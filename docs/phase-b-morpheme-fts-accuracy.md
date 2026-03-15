# Phase B: Morpheme FTS Before/After 정확도

## 📌 개요

Phase B는 **PostgreSQL FTS(Sparse) 레이어**에 kiwipiepy 형태소 분석을 적용합니다.

- **대상**: `chunks.tsv` (tsvector) 생성 + FTS 쿼리
- **핵심**: INSERT 시 `morpheme_tokenize(content)`, QUERY 시 `morpheme_tokenize(query)` — 양방향 동일 토크나이저
- **Phase A와의 차이**: Phase A는 Python keyword rescoring 레이어, Phase B는 DB FTS 레이어

---

## 🔴 Phase A 잔존 문제 (Before Phase B)

```
사용자 쿼리: "채용공고를"

plainto_tsquery('simple', '채용공고를') → tsquery: '채용공고를' (단일 토큰)
to_tsvector('simple', '채용 공고 안내') → '공고' | '안내' | '채용'

'채용공고를' ∉ {'채용', '공고', '안내'} → sparse_score = 0  ❌
```

복합어 + 조사가 붙은 쿼리는 **FTS에서 항상 0점** — dense score만으로 검색됨.

---

## 🟢 Phase B 솔루션 (After)

```
morpheme_tokenize('채용공고를') → '채용 공고'   (kiwipiepy: 복합어 분리 + 조사 제거)

plainto_tsquery('simple', '채용 공고') → '채용' & '공고'
'채용' ∈ tsvector AND '공고' ∈ tsvector → sparse_score > 0  ✅
```

---

## 📊 Before / After 점수 비교

> sparse_score 기준 (FTS 레이어 단독 효과)
> final_score = 0.7 × dense + 0.3 × (0.5 × sparse_norm + 0.5 × keyword_overlap)

### 복합어 쿼리

| 쿼리 | 저장 tsvector 토큰 | Before sparse | After sparse | 향상 |
|------|-------------------|:-------------:|:------------:|:----:|
| `채용공고를` | 채용, 공고, 안내 | 0 | ✅ 매칭 | 0 → signal |
| `개발자채용` | 개발자, 채용, 공고 | 0 | ✅ 매칭 | 0 → signal |
| `입사지원서` | 입사, 지원, 서류, 안내 | 0 | ✅ 매칭 | 0 → signal |

**이유**: simple 사전은 `채용공고를`을 단일 토큰으로 처리 → tsvector에 없음

---

### 조사 포함 쿼리

| 쿼리 | 저장 tsvector 토큰 | Before sparse | After sparse | 향상 |
|------|-------------------|:-------------:|:------------:|:----:|
| `증권에서` | 증권, 거래, 플랫폼 | 0 | ✅ 매칭 | 0 → signal |
| `백엔드에서` | 백엔드, 개발, 경력 | 0 | ✅ 매칭 | 0 → signal |
| `스타트업에서의` | 스타트업, 채용, 개발자 | 0 | ✅ 매칭 | 0 → signal |
| `머신러닝으로` | 머신러닝, AI, 데이터 | 0 | ✅ 매칭 | 0 → signal |

---

### 한영 혼합 쿼리

| 쿼리 | 저장 tsvector 토큰 | Before sparse | After sparse | 향상 |
|------|-------------------|:-------------:|:------------:|:----:|
| `AI채용` | AI, 채용, 스타트업 | 0 (단일 토큰) | ✅ 매칭 | 0 → signal |
| `Python백엔드` | Python, 백엔드, 개발 | 0 | ✅ 매칭 | 0 → signal |
| `LLM활용` | LLM, 활용, AI | 0 | ✅ 매칭 | 0 → signal |

**이유**: `AI채용`은 simple 사전에서 `ai채용` 단일 토큰 → kiwipiepy가 `AI` + `채용`으로 분리

---

### 정밀도(Precision) 유지 확인

| 쿼리 | 무관한 컨텐츠 | Before | After | 판정 |
|------|-------------|:------:|:-----:|:----:|
| `채용공고를` | 파이썬 비동기 프로그래밍 | no match | no match | ✅ 오매칭 없음 |
| `증권에서` | Python asyncio 완전 정복 | no match | no match | ✅ 오매칭 없음 |

---

## 📈 종합 효과 요약

| 케이스 | Phase A (particle strip) | Phase B (morpheme FTS) | 누적 효과 |
|--------|:------------------------:|:----------------------:|:---------:|
| 복합어 쿼리 | keyword overlap 개선 | ⭐ sparse signal 복구 | 양쪽 모두 작동 |
| 조사 포함 쿼리 | keyword overlap 개선 | ⭐ sparse signal 복구 | 양쪽 모두 작동 |
| 한영 혼합 | keyword overlap 개선 | ⭐ sparse signal 복구 | 양쪽 모두 작동 |
| 정밀도 | 유지 | 유지 | 회귀 없음 ✅ |
| 순수 영어 쿼리 | 해당 없음 | 해당 없음 | 변화 없음 |

**Phase B 핵심**: sparse_score가 `0`에서 `실질 signal`로 복구됨 → 기존에 dense에만 의존하던 검색이 FTS 결과도 활용

---

## 🔧 구현 위치

```
app/infrastructure/rag/
  └── korean_utils.py
      └── morpheme_tokenize(text) → str  # kiwipiepy NN/VV/SL/XR 추출

app/infrastructure/repository/
  └── chunk_repository.py
      ├── save_chunks: to_tsvector('simple', morpheme_tokenize(content))
      └── search_similar: plainto_tsquery('simple', morpheme_tokenize(query_text))

alembic/versions/
  └── 0006_rebuild_tsvectors_with_morpheme_tokenization.py  # no-op (DDL 없음)

scripts/
  └── backfill_morpheme_tsvectors.py  # 기존 chunks 1회 백필
```

---

## 🧪 테스트

```bash
pytest tests/test_phase_b_morpheme_accuracy.py -v
# 13 passed — before/after accuracy + recall/precision parametrize
```

| 테스트 | 검증 내용 |
|--------|---------|
| `test_morpheme_tokenize_splits_compound_word` | `채용공고` → `채용`, `공고` 분리 |
| `test_morpheme_tokenize_strips_particle_from_compound` | `채용공고를` → raw form 제거 |
| `test_morpheme_tokenize_simple_noun` | `증권에서` → `증권` |
| `test_morpheme_tokenize_preserves_english` | `AI 개발자를` → `AI`, `개발자` 유지 |
| `test_fts_accuracy_before_after_compound_query` | no-match → match 시뮬레이션 |
| `test_fts_accuracy_before_after_particle_query` | no-match → match 시뮬레이션 |
| `test_morpheme_tokenize_precision_not_degraded` | 무관 쿼리 false positive 없음 |
| `test_morpheme_tokenize_recall_precision_table` | 4개 케이스 parametrize |

---

## 📚 관련 문서

- [Phase A: Korean Morpheme Handling](./korean-morpheme-handling.md)
- [Korean Morpheme Plan](./../.omc/plans/korean-morpheme-hybrid-search.md)
