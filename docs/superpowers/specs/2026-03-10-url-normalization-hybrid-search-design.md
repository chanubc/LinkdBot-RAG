# 설계 문서: URL 정규화 & Hybrid Search 개선

**작성일:** 2026-03-10
**관련 이슈:** URL 중복 저장 버그, 한국어 Hybrid Search 미동작
**브랜치:** refactor/#66-llm-consistency (또는 신규 feat 브랜치)

---

## 배경 및 문제 정의

### 문제 1: URL 중복 저장

같은 콘텐츠 URL이 트래킹 파라미터 차이로 중복 저장되는 버그.

```
# 동일한 Threads 포스트가 다른 link_id로 2번 저장됨
https://www.threads.com/@user/post/ABC?xmt=SESSION1&slof=1  → link_id=10
https://www.threads.com/@user/post/ABC?xmt=SESSION2&slof=1  → link_id=11
```

`uq_user_url` UNIQUE 제약은 완전 일치 기준이라 파라미터가 달라지면 통과됨.

### 문제 2: 한국어 Hybrid Search 미동작

`plainto_tsquery('simple', '하나증권 관련 공고')` — `simple` 설정은 한국어 형태소 분석 미지원.
결과: FTS sparse 컴포넌트가 한국어 쿼리에서 사실상 0점 → Dense-only 검색으로 폴백.
증상: "하나증권 공고" 검색 시 "파이썬 로깅" 등 무관한 결과 상위 등장, 동일 링크 중복 노출.

---

## 설계

### 섹션 1: URL 정규화

**변경 파일:** `app/utils/url.py` (신규), `app/application/usecases/save_link_usecase.py`

**핵심 원칙:** 콘텐츠 식별에 무관한 트래킹 파라미터만 제거. 콘텐츠를 결정하는 파라미터(`?v=` for YouTube 등)는 보존.

**제거 대상 파라미터:**
```python
TRACKING_PARAMS = {
    # 소셜/광고 트래킹
    "xmt", "slof", "igsh", "igshid", "fbclid",
    # UTM
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    # 기타
    "_ga", "_gl", "source", "mc_cid", "mc_eid",
}
# ⚠️ "ref"는 제외: Amazon 등 일부 사이트에서 콘텐츠 식별에 사용됨 (false positive 위험)
```

**동작:**
```python
# app/utils/url.py
def normalize_url(url: str) -> str:
    parsed = urlparse(url)
    params = {k: v for k, v in parse_qs(parsed.query).items()
              if k.lower() not in TRACKING_PARAMS}
    clean_query = urlencode(params, doseq=True)
    return urlunparse(parsed._replace(query=clean_query))
```

**적용 지점:** `save_link_usecase.execute()` 진입부 1줄 추가.
```python
async def execute(self, telegram_id: int, url: str, ...) -> None:
    url = normalize_url(url)   # ← 추가
    if await self._link_repo.exists_by_user_and_url(...):
        ...
```
이후 중복 체크 → DB 저장 → Notion 저장 모두 정규화된 URL 사용.

**테스트 케이스:**
- `?xmt=ABC&slof=1` 제거됨
- YouTube `?v=VIDEO_ID` 보존됨
- 네이버 블로그 `?blogId=xxx` 보존됨
- 파라미터 없는 URL 그대로 반환됨
- URL fragment(`#section`) → 제거 (클라이언트 앵커는 콘텐츠 식별에 무관)
  - `urlunparse`에서 `fragment=""` 처리

---

### 섹션 2: Hybrid Search 개선 (FTS → LLM Keyword 매칭)

**변경 파일:** `app/infrastructure/rag/retriever.py`, `app/infrastructure/repository/chunk_repository.py` (SQL 컬럼 2개 추가)

**핵심 원칙:** 비즈니스 로직 변경 최소화. `l.keywords`, `l.content_source`, `d.dense_score` 컬럼만 SELECT에 추가.

> **SQL 변경 범위:** `chunk_repository.py`의 SELECT에 `d.dense_score`, `l.content_source` 2개 컬럼 추가 (각 1줄). 현재 반환되는 `similarity`는 이미 `dense*0.7 + sparse*0.3`으로 블렌딩된 값이므로, keyword 재스코어링을 위해 raw `dense_score`를 분리 반환해야 함.

**동작 흐름:**
```
1. Dense + FTS SQL (기존) → top_k=10 결과 반환
   (기존 FTS는 한국어에서 0점이지만 Dense는 동작하므로 유지)
   SQL SELECT에 d.dense_score, l.content_source 추가

2. Python에서 keyword_score 계산:
   - 쿼리를 공백으로 토큰화 → query_tokens (소문자)
   - result['keywords'] JSON 파싱 → link_keywords (소문자)
   - overlap = len(query_tokens ∩ link_keywords) / max(len(query_tokens), 1)

3. content_source 가중치 적용:
   - "jina" (본문 기반 키워드) → keyword_weight = 0.3
   - "og"  (메타태그 기반 키워드) → keyword_weight = 0.1

4. final_score = dense_score * (1 - keyword_weight) + overlap * keyword_weight

5. final_score 기준 재정렬 → SimpleReranker top_k=5 반환
```

**예시:**
```
query = "하나증권 관련 공고"
query_tokens = {"하나증권", "관련", "공고"}

링크 A (하나증권 채용): keywords=["하나증권", "AI직무", "채용공고", "금융", "취업"]
  → intersection = {"하나증권"} → overlap = 1/3 ≈ 0.33
  → final_score = dense(0.65) * 0.7 + 0.33 * 0.3 = 0.455 + 0.099 = 0.554 ✓

링크 B (파이썬 로깅): keywords=["Python", "로깅", "logging", "개발", "모범사례"]
  → intersection = {} → overlap = 0
  → final_score = dense(0.58) * 0.7 + 0 * 0.3 = 0.406 ✗ (정상 하락)
```

**변경 범위:**
- `HybridRetriever.retrieve()` 에 keyword 스코어링 로직 추가 (~20줄)
- `ChunkRepository.search_similar()` SQL에 `l.content_source` 컬럼 추가 반환 (1줄)
- `SimpleReranker`는 변경 없음 (이미 similarity 내림차순 정렬)

---

## 영향 범위

| 컴포넌트 | 변경 | 비고 |
|---|---|---|
| `app/utils/url.py` | 신규 생성 | |
| `app/application/usecases/save_link_usecase.py` | 1줄 추가 | `normalize_url(url)` 호출 |
| `app/infrastructure/rag/retriever.py` | keyword 스코어링 추가 | ~20줄 |
| `app/infrastructure/repository/chunk_repository.py` | `d.dense_score`, `l.content_source` SELECT 추가 | 2줄 |
| DB 스키마 | 변경 없음 | |
| 기존 테스트 | 영향 최소 | URL 관련 테스트 일부 수정 필요 |

---

## 미포함 항목 (다음 이슈)

- BM25 기반 keyword 스코어링 (추후 정밀도 개선 시 고려)
- 한국어 복합어 부분 매칭: 쿼리 토큰 "공고"가 키워드 "채용공고"와 매칭되지 않음 (exact match 방식 한계). substring 매칭 또는 형태소 분석기(Kiwi) 도입 시 개선 가능 — 현재 범위에서 제외
- 기존 중복 링크 DB 정리 스크립트
- Notion child page 본문 추가 (#1)
- Telegram Button UI (#3)
- Dashboard 홈 리디자인 (#6, #7)
