# 한국어 Hybrid Search 개선 요약

## 문제상황

기존 Hybrid Search는 Dense score와 PostgreSQL FTS 기반 sparse score를 함께 사용했지만,
PostgreSQL `simple` FTS가 한국어 형태소 분석을 제대로 지원하지 못해
한국어 질의에서는 sparse score가 거의 기여하지 못했다.

또한 DB가 먼저 `top_k`만큼만 후보군을 잘라서 반환했기 때문에,
keyword relevance가 높은 문서라도 초기 dense 순위가 낮으면 최종 결과에서 복구되지 못했다.

즉, 한국어 환경에서는 Hybrid Search가 실제로는 Dense-only에 가깝게 동작하는 문제가 있었다.

---

## 해결방안

1. **후보군 확대 (`recall_k`)**
   - `recall_k = min(max(top_k * 5, 30), 100)`
   - `top_k=5` 요청 시 최소 30개 후보를 먼저 조회하도록 변경

2. **keyword overlap 기반 재스코어링**
   - query token과 문서 keyword overlap을 계산
   - dense score와 결합해 최종 점수 재산출
   - source별 가중치 적용
     - `jina`: 0.3
     - `og`: 0.1

이 구조를 통해 초기 후보군 밖으로 밀리던 관련 문서를 최종 상위 결과로 복구할 수 있게 했다.

---

## 성과

한국어 relevance failure scenario 12건으로 구성한 오프라인 benchmark 기준:

- **Top-1 Accuracy:** 16.7% → 83.3% (**+66.6%p**)
- **Recall@5:** 16.7% → 83.3% (**+66.6%p**)
- **MRR@5:** 0.167 → 0.833 (**+0.666**)
- **후보군 크기:** `top_k=5` 기준 5개 → 30개 (**6배 확대**)

추가로,
- 검색 관련 테스트 **29 passed**
- 전체 테스트 **93 passed**
를 확인했다.

---

## 현재 버전 한계

후보군 확보와 keyword relevance 반영은 크게 개선되었지만,
`공고` ↔ `채용공고`, `AI 직무` ↔ `AI직무` 같은
한국어 복합어 / 형태소 문제는 여전히 일부 남아 있다.

따라서 이후에는 형태소 분석기(Kiwi 등) 또는 BM25 기반 고도화를 검토할 수 있다.

---

## Resume Summary

- 한국어 형태소 분석 한계로 sparse score가 거의 작동하지 않던 Hybrid Search를 **후보군 확장 + keyword 재스코어링**으로 개선
- 오프라인 benchmark 기준 **Top-1 Accuracy 16.7% → 83.3%**, **MRR@5 0.167 → 0.833** 향상
- `top_k=5` 기준 검색 후보군을 **5개 → 30개(6배)** 로 확대해 관련 문서가 초기 후보군 밖으로 탈락하는 문제 완화

---

## STAR Summary

- **Situation**: PostgreSQL `simple` FTS의 한국어 형태소 분석 한계로 Hybrid Search가 사실상 Dense-only처럼 동작해, 한국어 질의에서 관련 문서가 상위에 노출되지 않는 문제가 있었음
- **Task**: 기존 검색 아키텍처를 크게 변경하지 않고 한국어 검색 relevance를 개선해야 했음
- **Action**: 검색 후보군을 `recall_k` 기반으로 확장하고, keyword overlap 재스코어링 및 source별 가중치(`jina=0.3`, `og=0.1`)를 적용해 ranking 로직 개선
- **Result**: 오프라인 benchmark 기준 **Top-1 Accuracy 16.7% → 83.3%(+66.6%p)**, **Recall@5 16.7% → 83.3%(+66.6%p)**, **MRR@5 0.167 → 0.833** 개선
