# 한국어 Hybrid Search 품질 개선

## 현재 버전 기준 요약

현재 버전에서는 한국어 질의에서 사실상 Dense-only처럼 동작하던 Hybrid Search를 개선하기 위해,
후보군 확장(`recall_k`)과 keyword overlap 기반 재스코어링을 도입했다.

핵심은 다음 두 가지다.

1. DB가 너무 이른 단계에서 `top_k`만큼 잘라 버리던 문제를 해결하기 위해 후보군을 더 넓게 조회
2. PostgreSQL `simple` FTS의 한국어 형태소 분석 한계를 보완하기 위해 Python 레벨 keyword overlap 점수를 최종 점수에 반영

이로 인해 한국어 relevance failure scenario 기준에서 상위 결과 정확도가 크게 향상되었다.

---

## 문제 상황

기존 검색은 다음 두 신호를 결합하는 Hybrid Search 구조였다.

- Dense score: 임베딩 기반 의미 유사도
- Sparse score: PostgreSQL FTS 기반 키워드 매칭 점수

하지만 PostgreSQL `plainto_tsquery('simple', ...)`는 한국어 형태소 분석을 지원하지 않기 때문에,
한국어 질의에서는 sparse score가 거의 기여하지 못했다.

예를 들어 다음과 같은 문제가 발생할 수 있었다.

- `하나증권 채용`
- `금융권 AI 공고`
- `RAG chunking 전략`

이런 질의에서 키워드 관점으로는 관련성이 높은 문서가 있어도,
초기 dense 순위가 약간 밀리면 DB 후보군 밖으로 떨어지고 최종 결과에서 복구되지 못했다.

즉, 구조는 Hybrid Search였지만 한국어 환경에서는 실제로 **Dense Search에 가까운 결과**를 내는 문제가 있었다.

---

## 원인 분석

### 1. 한국어 형태소 분석 부재

PostgreSQL `simple` FTS는 한국어를 의미 단위로 잘 분해하지 못한다.

예를 들면 다음과 같은 표현 차이를 잘 처리하지 못한다.

- `공고` ↔ `채용공고`
- `AI 직무` ↔ `AI직무`
- `하나증권` ↔ `하나증권은`

사람 입장에서는 유사한 표현이지만,
형태소 분석이 없으면 서로 다른 토큰으로 취급되어 sparse score가 거의 붙지 않는다.

### 2. 후보군이 너무 빨리 잘리는 구조

기존 방식은 DB가 먼저 `top_k`만큼 결과를 제한한 뒤,
그 결과에 대해서만 후처리를 수행했다.

이 구조에서는 keyword relevance가 높은 문서라도 초기 dense 순위가 낮으면
후보군에 포함되지 못하고, 이후 단계에서 절대 상위로 올라올 수 없었다.

---

## 해결 방안

## 1. 후보군 확대 (`recall_k`)

최종 반환 개수(`top_k`)와 별도로, DB에서는 더 넓은 후보군을 먼저 조회하도록 변경했다.

- 공식:
  - `recall_k = min(max(top_k * 5, 30), 100)`

예를 들어 `top_k=5` 요청 시:

- 기존 후보군: 5개
- 개선 후 후보군: 최소 30개

즉, 후보군을 **6배 확대**해 dense 순위만으로 탈락하던 문서도 재정렬 대상에 포함시켰다.

---

## 2. keyword overlap 기반 재스코어링

넓게 확보한 후보군에 대해 Python 레벨에서 keyword overlap 점수를 계산하고,
이를 dense score와 결합해 최종 순위를 다시 계산했다.

### 최종 점수

- `final_score = dense_score * (1 - weight) + overlap * weight`

### source별 가중치

- `jina`: `0.3`
- `og`: `0.1`

이 가중치 분리는 본문 기반 키워드(`jina`)가 메타태그 기반 키워드(`og`)보다
더 신뢰도 높다고 판단한 결과다.

---

## 구현 내용

### 주요 변경 파일

- `app/infrastructure/rag/retriever.py`
- `app/infrastructure/repository/chunk_repository.py`
- `tests/test_retriever.py`

### 주요 구현 포인트

- `top_k` 대신 `recall_k` 기반 후보군 조회
- keyword overlap 기반 재스코어링 추가
- source별 keyword weight 차등 적용
- 비정상 keywords JSON 방어 처리
- dense 순위는 낮지만 keyword relevance로 최종 상위에 올라오는 테스트 추가

---

## 정량 성과

## 오프라인 Benchmark 기준

운영 로그 기반이 아닌,
**한국어 relevance failure scenario 12건으로 구성한 오프라인 benchmark**에서 before / after를 비교했다.

### 비교 조건

- Before
  - DB 후보군 제한 10
  - 그 안에서만 rescoring
- After
  - 후보군 확대(`recall_k`)
  - keyword overlap 재스코어링 적용

### 결과

#### Top-1 Accuracy
- Before: **16.7%**
- After: **83.3%**
- 개선폭: **+66.6%p**

#### Recall@5
- Before: **16.7%**
- After: **83.3%**
- 개선폭: **+66.6%p**

#### MRR@5
- Before: **0.167**
- After: **0.833**
- 개선폭: **+0.666**

#### 후보군 크기
- `top_k=5` 기준: **5개 → 30개**
- 후보군 **6배 확대**

---

## 테스트 결과

- 검색 관련 테스트: **29 passed**
- 전체 테스트: **93 passed**
- warning 1건
  - `datetime.utcnow()` deprecation
  - 이번 검색 개선과 직접 관련 없음

---

## 한계와 후속 과제

이번 개선으로 후보군 확보와 keyword relevance 반영 문제는 크게 개선했지만,
한국어 복합어 / 형태소 분해 문제를 완전히 해결한 것은 아니다.

오프라인 benchmark에서도 다음과 같은 케이스는 여전히 한계가 남는다.

- `공고` ↔ `채용공고`
- `AI 직무` ↔ `AI직무`

따라서 후속 단계에서는 아래를 검토할 수 있다.

- 한국어 형태소 분석기(Kiwi 등) 도입
- BM25 기반 sparse 검색 고도화
- substring / token normalization 개선

---

## 한 줄 요약

한국어 형태소 분석 한계로 사실상 Dense-only처럼 동작하던 Hybrid Search를,
**후보군 6배 확대 + keyword overlap 재스코어링**으로 개선해,
오프라인 benchmark 기준 **Top-1 Accuracy 16.7% → 83.3%**까지 향상시켰다.

---

## Resume Summary

- PostgreSQL `simple` FTS의 한국어 형태소 분석 한계로 Hybrid Search가 사실상 Dense-only처럼 동작하던 문제를 분석하고, **후보군 확장(`recall_k`) + keyword overlap 재스코어링** 구조로 개선
- 검색 후보군을 `top_k=5` 기준 **5개 → 30개(6배)** 로 확대하고, source별 keyword weight(`jina=0.3`, `og=0.1`)를 적용해 한국어 relevance ranking 보완
- 한국어 relevance scenario 12건 오프라인 benchmark 기준 **Top-1 Accuracy 16.7% → 83.3%(+66.6%p)**, **Recall@5 16.7% → 83.3%(+66.6%p)**, **MRR@5 0.167 → 0.833** 개선
