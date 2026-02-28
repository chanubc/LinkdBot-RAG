# 🚀 Phase 3 — Proactive Intelligence Layer
_Jina AI Reader + Hybrid RAG 기반 관심사 분석 & 재활성화 시스템_

---

# 🎯 Phase 3 목표

Phase 3의 핵심 목적은:

> 사용자가 저장했지만 잊어버린 지식을  
> 현재 관심사 변화(Drift)를 기반으로  
> 가장 적절한 시점에 다시 상기시켜주는 것

Phase 3에서 구현할 요소:

- Jina AI 기반 본문 품질 향상
- Hybrid RAG 도입 (Dense + Sparse)
- Interest Drift 계산
- Reactivation Score 계산
- Weekly Proactive Report 발송

---

# 🧠 핵심 철학

Phase 3는 "미래 예측 시스템"이 아니다.

우리가 구현하는 것은:

> 과거 저장 데이터 기반  
> 현재 관심 상태 추정 + 망각 보정 시스템

---

# 📦 전체 아키텍처 흐름

Telegram Link
    ↓
Webhook 수신 (즉시 200 OK)
    ↓
Background Task
    ↓
Jina Reader 본문 수집
    ↓
Clean & Chunk
    ↓
Embedding (Summary + Chunk)
    ↓
pgvector 저장
    ↓
Hybrid RAG
    ↓
Drift 분석
    ↓
Reactivation 추천
    ↓
Weekly Push

---

# 1️⃣ Jina AI Reader 도입

## 1.1 환경 변수 설정

.env

```env
JINA_API_KEY=jina_xxxxxxxxx
```

---

## 1.2 WebScraperPort 정의

app/application/ports/web_scraper_port.py

```python
from abc import ABC, abstractmethod

class WebScraperPort(ABC):
    @abstractmethod
    async def extract_markdown(self, url: str) -> str:
        pass
```

---

## 1.3 JinaReaderAdapter 구현

app/infrastructure/external/jina_reader_adapter.py

```python
import httpx
import logging
from app.application.ports.web_scraper_port import WebScraperPort

logger = logging.getLogger(__name__)

class JinaReaderAdapter(WebScraperPort):

    def __init__(self, api_key: str | None = None):
        self.base_url = "https://r.jina.ai/"
        self.headers = {
            "Authorization": f"Bearer {api_key}" if api_key else "",
            "X-Return-Format": "markdown"
        }

    async def extract_markdown(self, url: str) -> str:
        timeout = httpx.Timeout(connect=5.0, read=15.0, write=5.0)

        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(
                    f"{self.base_url}{url}",
                    headers=self.headers,
                )
                response.raise_for_status()

                content = response.text.strip()
                if not content:
                    return self._fallback(url)

                return content

        except Exception as e:
            logger.warning(f"Jina failed for {url}: {e}")
            return self._fallback(url)

    def _fallback(self, url: str) -> str:
        # TODO: bs4 기반 article 추출 로직 추가
        return f"본문 추출 실패: {url}"
```

---

## 1.4 content_source 필드 추가

```sql
ALTER TABLE links
ADD COLUMN content_source VARCHAR;
```

값:

- 'jina'
- 'bs4'
- 'og'

---

# 2️⃣ Embedding 전략 개선

## 2.1 summary_embedding 컬럼 추가

```sql
ALTER TABLE links
ADD COLUMN summary_embedding VECTOR(1536);
```

이 필드는:

- Drift centroid 계산
- Reactivation similarity 계산
- 빠른 유사도 검색

에 사용된다.

---

## 2.2 Chunk 전략

- chunk_size: 800~1000
- overlap: 100~150
- MarkdownTextSplitter 사용 권장

```python
from langchain.text_splitter import MarkdownTextSplitter

def split_markdown(content: str):
    splitter = MarkdownTextSplitter(
        chunk_size=900,
        chunk_overlap=120
    )
    return splitter.split_text(content)
```

---

## 2.3 Bulk Embedding (반드시 batch)

```python
embeddings = embed(chunks)
```

N번 호출 금지.

---

# 3️⃣ Hybrid RAG 도입

## 3.1 Dense Search (pgvector cosine)

```sql
ORDER BY embedding <=> :query_embedding
```

---

## 3.2 Sparse Search 추가 (Full Text Search)

```sql
ALTER TABLE chunks
ADD COLUMN tsv tsvector;

CREATE INDEX idx_chunks_tsv
ON chunks USING GIN(tsv);
```

저장 시:

```sql
to_tsvector('english', content)
```

---

## 3.3 Hybrid 점수 계산

FinalScore =

(DenseScore × 0.7)
+
(SparseScore × 0.3)

---

# 4️⃣ Interest Drift 계산

정의:

D(c) = P_current(c) - P_past(c)

TVD = 0.5 × Σ|D(c)|

기간:

- current: 최근 7일
- past: 최근 30일

조건:

- 최근 7일 링크 ≥ 3개
- ALLOWED_CATEGORIES 고정 사용

---

# 5️⃣ Current Interest Centroid

최근 7일 summary_embedding 평균 계산.

Fallback:

- 최근 7일 없음 → 전체 링크 평균

---

# 6️⃣ Reactivation Logic

## 필터 조건

- is_read = False
- created_at <= now - 7days

---

## 점수 공식

Score =

(Similarity × 0.6)
+
(ForgettingScore × 0.4)

Where:

Similarity = cosine(current_centroid, summary_embedding)

ForgettingScore =
1 - (1 / (1 + days_since_created))

---

## 선택

Score 최고 1개 선택.

중복 추천 방지:

- 최근 14일 추천된 링크 제외

---

# 7️⃣ Weekly Report UseCase

GenerateWeeklyReportUseCase

Flow:

1. Drift 계산
2. 가장 큰 D(c) 카테고리 추출
3. Reactivation 링크 선정
4. LLM 요약 생성
5. Telegram Push

---

# 8️⃣ Scheduler

권장:

- APScheduler
- 매주 일요일 20:00 실행

---

# 9️⃣ 기존 데이터 재처리

권장:

- 최근 30일 링크 재처리
- summary_embedding 생성
- chunk 재임베딩

---

# 🔟 Phase 3 완료 조건

✔ Jina 기반 본문 수집  
✔ summary_embedding 저장  
✔ Hybrid RAG 적용  
✔ Drift 계산 구현  
✔ Reactivation 추천 구현  
✔ Weekly Push 구현  

---

# ⚠ 운영 시 주의사항

- 최근 데이터 부족 시 Drift skip
- 유저 데이터 부족 시 Weekly skip
- Jina 실패율 모니터링
- embedding batch size 최적화

---

# 🏁 최종 목표

과거 지식 → 현재 관심 분석 →  
적절한 시점에 재상기 →  
지속적인 개인화 지식 루프 구축