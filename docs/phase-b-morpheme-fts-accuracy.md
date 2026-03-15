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

## 📊 실측 벤치마크 결과

> **측정 환경**: 라이브 DB (2,614 chunks), `scripts/benchmark_fts_accuracy.py`
> **Ground truth**: 쿼리 어근이 chunk content에 포함된 chunks
> **Before**: `plainto_tsquery('simple', raw_query)`
> **After**: `plainto_tsquery('simple', morpheme_tokenize(query))`

### 쿼리별 상세 결과

| 쿼리 | 형태소 변환 | 관련 chunks | P@5 Before | P@5 After | MRR Before | MRR After | NDCG@5 Before | NDCG@5 After | 1위 Before | 1위 After |
|------|------------|:-----------:|:----------:|:---------:|:----------:|:---------:|:-------------:|:------------:|:----------:|:---------:|
| `채용공고를` | `채용 공고` | 114 | 0.0000 | **1.0000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |
| `개발자채용` | `개발자 채용` | 160 | 0.0000 | **0.4000** | 0.0000 | **1.0000** | 0.0000 | **0.5531** | ❌ | ✅ |
| `입사지원서` | `입사 지원서` | 173 | 0.0000 | **1.0000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |
| `백엔드에서` | `백 엔드` | 4 | 0.0000 | **0.8000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |
| `증권에서` | `증권` | 17 | 0.0000 | **1.0000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |
| `스타트업에서의` | `스타트업` | 5 | 0.0000 | **1.0000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |
| `머신러닝으로` | `머신 러닝` | 9 | 0.0000 | **0.8000** | 0.0000 | **1.0000** | 0.0000 | **0.8304** | ❌ | ✅ |
| `AI채용` | `AI 채용` | 1,481 | 0.0000 | **1.0000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |
| `Python백엔드` | `Python 백 엔드` | 148 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | 0.0000 | ❌ | ❌ |
| `LLM활용` | `LLM 활용` | 142 | 0.0000 | **1.0000** | 0.0000 | **1.0000** | 0.0000 | **1.0000** | ❌ | ✅ |

### 종합 지표

| 지표 | Before (Phase A) | After (Phase B) | 향상 |
|------|:----------------:|:---------------:|:----:|
| **P@5** | 0.0000 | **0.8000** | 0 → 0.80 |
| **MRR** | 0.0000 | **0.9000** | 0 → 0.90 |
| **NDCG@5** | 0.0000 | **0.8384** | 0 → 0.84 |
| **1위 정확도** | 0/10 (0%) | **9/10 (90%)** | **+900%p** |

> **Before는 10개 쿼리 전부 sparse_score = 0** — FTS 레이어가 완전히 무력했음

---

## ⚠️ 예외 케이스: `Python백엔드`

`Python백엔드` → kiwipiepy가 `Python 백 엔드`로 분리 (백엔드를 "백" + "엔드"로 잘못 분리)

- `백 엔드`로 조회 시 content에 "백"과 "엔드"가 함께 있는 chunks가 없어서 0점
- **원인**: `백엔드`는 영어 loanword지만 한글 표기라 kiwipiepy가 음절 단위로 분리
- **Phase C 개선 대상**: 외래어 사전 추가 또는 사용자 정의 사전(kiwipiepy `add_user_word`)

---

## 📈 Phase A vs Phase B 레이어 비교

| 검색 레이어 | Phase A | Phase B |
|-----------|:-------:|:-------:|
| Dense (pgvector) | ✅ 정상 | ✅ 정상 |
| Sparse FTS | ❌ 복합어/조사 쿼리 0점 | ✅ 90% 복구 |
| Keyword rescoring | ✅ 조사 처리 | ✅ 유지 |

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

scripts/
  ├── backfill_morpheme_tsvectors.py   # 기존 chunks 1회 백필 (완료: 2,614건)
  └── benchmark_fts_accuracy.py        # 정확도 벤치마크
```

---

## 🧪 테스트

```bash
# 단위 테스트
pytest tests/test_phase_b_morpheme_accuracy.py -v

# 라이브 벤치마크
python scripts/benchmark_fts_accuracy.py --user-id <TELEGRAM_ID>
```

---

## 📚 관련 문서

- [Phase A: Korean Morpheme Handling](./korean-morpheme-handling.md)
- [Korean Morpheme Plan](./../.omc/plans/korean-morpheme-hybrid-search.md)
