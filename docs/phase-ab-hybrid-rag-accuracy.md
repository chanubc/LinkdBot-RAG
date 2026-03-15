# Phase A/B Hybrid RAG 실사용 쿼리 정확도

## 📌 측정 목표

실제 사용자가 자연어로 쿼리를 날렸을 때 **적합한 링크가 상위에 오는지** 측정합니다.
Dense(pgvector) + Sparse(FTS) + Keyword Rescoring 전체 파이프라인 기준입니다.

> 형태소 단위 FTS 정확도는 [`phase-b-morpheme-fts-accuracy.md`](./phase-b-morpheme-fts-accuracy.md) 참고.

---

## 측정 환경

| 항목 | 내용 |
|------|------|
| 스크립트 | `scripts/benchmark_hybrid_rag.py` |
| 라이브 DB | 2,614 chunks, 약 150+ links |
| 쿼리 유형 | 복합어+조사 포함 자연어 쿼리 10개 |
| Ground truth | 쿼리 관련 링크 제목 키워드 기반 수동 레이블 |
| 임베딩 | OpenAI text-embedding-3-small |
| Top-K | 5 |

### 단계 정의

| 단계 | FTS 전략 | Keyword Rescoring |
|------|---------|------------------|
| **Pre-Phase A** | raw query | raw 토큰 매칭 |
| **Phase A** | raw query | morpheme 변형 + `_token_matches` |
| **Phase B** | morpheme_tokenize(query) | morpheme 변형 + `_token_matches` |

---

## 📊 실측 결과

### 쿼리별 상세 (MRR 기준)

| 쿼리 | 쿼리 유형 | 관련 | P@5 Pre-A | P@5 Ph-A | P@5 Ph-B | MRR Pre-A | MRR Ph-A | MRR Ph-B | Top-1 Pre-A | Top-1 Ph-A | Top-1 Ph-B |
|------|---------|:---:|:---------:|:--------:|:--------:|:---------:|:--------:|:--------:|:-----------:|:----------:|:----------:|
| `삼성에서 신입공채 자소서를 써야해` | 에서/를 조사 | 4 | 0.40 | 0.40 | 0.40 | 1.00 | 1.00 | 1.00 | ✅ | ✅ | ✅ |
| `롯데채용공고를 찾아줘` | 복합어+를 | 1 | 0.00 | **0.20** | **0.20** | 0.00 | **1.00** | **1.00** | ❌ | ✅ | ✅ |
| `한화시스템에서 ICT채용한다는데` | 에서+복합어 | 2 | 0.20 | **0.40** | **0.40** | 1.00 | 1.00 | 1.00 | ✅ | ✅ | ✅ |
| `개발자채용을 하는 AI스타트업` | 복합어+을 | 55 | 0.60 | 0.60 | 0.60 | 0.50 | 0.50 | 0.50 | ❌ | ❌ | ❌ |
| `AI개발자를 뽑는 회사 알려줘` | 복합어+를 | 55 | 0.80 | 0.80 | 0.80 | 0.50 | **1.00** | **1.00** | ❌ | ✅ | ✅ |
| `Claude코드로 개발하는 방법` | 복합어+로 | 18 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | ✅ | ✅ | ✅ |
| `파이썬으로 개발하는 공식 튜토리얼` | 외래어 한글+로 | 3 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 | ❌ | ❌ | ❌ |
| `LLM에이전트 개념이 뭐야` | 한영복합+이 | 50 | 0.80 | 0.80 | 0.80 | 1.00 | 1.00 | 1.00 | ✅ | ✅ | ✅ |
| `AI코딩워크플로우 도구를 찾아줘` | 복합어+를 | 46 | 0.60 | **0.80** | **0.80** | 0.50 | **1.00** | **1.00** | ❌ | ✅ | ✅ |
| `GCP에서 크레딧 관리하는법` | 에서 조사 | 1 | 0.20 | 0.20 | 0.20 | 1.00 | 1.00 | 1.00 | ✅ | ✅ | ✅ |

### 종합 지표

| 지표 | Pre-Phase A | Phase A | Phase B | Pre-A → A | Pre-A → B |
|------|:-----------:|:-------:|:-------:|:---------:|:---------:|
| **P@5** | 0.4600 | **0.5200** | **0.5200** | **+13%** | **+13%** |
| **MRR** | 0.6500 | **0.8500** | **0.8500** | **+31%** | **+31%** |
| **NDCG@5** | 0.5758 | **0.7523** | **0.7523** | **+31%** | **+31%** |
| **Top-1 정확도** | 5/10 (50%) | **8/10 (80%)** | **8/10 (80%)** | **+60%** | **+60%** |

---

## 분석

### Phase A = Phase B (Hybrid RAG 기준)

Hybrid 파이프라인에서 **Phase A와 Phase B의 결과가 동일**합니다.

이유: Phase A의 `_build_query_variants()`가 `morpheme_tokenize()`로 변형을 생성해
keyword rescoring 레이어에서 이미 복합어/조사 처리를 수행하기 때문입니다.
Phase B의 FTS 개선은 dense + keyword가 이미 올바른 순위를 잡은 상태에서
추가 delta를 만들지 못합니다.

```
Phase A keyword rescoring:
  "롯데채용공고를" → variants: ["롯데채용공고를", "롯데채용공고", "롯데 채용 공고", ...]
  → "롯데" in link.keywords → overlap 증가 → 롯데이노베이트 링크 상위 이동 ✅

Phase B FTS:
  plainto_tsquery('simple', '롯데 채용 공고') → FTS 매칭
  → 이미 keyword rescoring이 올바른 순위를 잡았으므로 추가 변화 없음
```

### Phase B가 단독으로 기여하는 경우

Phase B FTS는 다음 상황에서 keyword rescoring과 독립적으로 기여합니다:

| 상황 | 설명 |
|------|------|
| `link.keywords`가 없는 chunks | LLM이 키워드 추출 실패한 링크 |
| chunks만 있고 title 매칭 불가 | 링크 제목에 쿼리 어근 없는 경우 |
| 긴 문서의 특정 단락 검색 | title/keyword가 부분적일 때 chunk content FTS로 보완 |

### 실패 케이스 분석

**`파이썬으로 개발하는 공식 튜토리얼` → 0점**
- DB 링크 제목: "Python 3.14.3 Official Tutorial" (영문)
- 쿼리의 "파이썬"이 "Python"과 매칭 불가 (한/영 표기 불일치)
- Dense는 의미적으로 유사하게 처리하나 keyword/FTS 레이어에서 실패
- **Phase C 개선 대상**: 한영 동의어 사전 (`파이썬` ↔ `Python`)

**`개발자채용을 하는 AI스타트업` → Top-1 ❌ (전 단계)**
- 관련 링크가 55개로 너무 많아 특정 Top-1을 정의하기 어려움
- MRR=0.5 (2위 이내 존재) → 실용적으로는 허용 가능한 수준

---

## 레이어별 기여 정리

| 레이어 | Pre-Phase A | Phase A | Phase B |
|--------|:-----------:|:-------:|:-------:|
| Dense (pgvector) | ✅ 동일 | ✅ 동일 | ✅ 동일 |
| Sparse FTS | ❌ 복합어 0점 | ❌ 동일 | ✅ 복구 (chunk-only 경우) |
| Keyword rescoring | ❌ 조사 실패 | ✅ morpheme 변형 | ✅ 동일 |
| **최종 개선** | 기준 | **MRR +31%, Top-1 +60%** | **동일** |

---

## 결론

- **실사용 쿼리 기준 주요 개선**: Phase A (keyword rescoring morpheme 변형)
- **Phase B 추가 가치**: chunk content 기반 FTS 보완 (keyword 없는 문서 coverage 확대)
- **미해결 과제**: 한영 표기 불일치 (`파이썬` ↔ `Python`) → Phase C 동의어 사전

---

## 📚 관련 문서

- [FTS 레이어 단독 정확도 (Phase B)](./phase-b-morpheme-fts-accuracy.md)
- [Phase A: Korean Morpheme Handling](./korean-morpheme-handling.md)
