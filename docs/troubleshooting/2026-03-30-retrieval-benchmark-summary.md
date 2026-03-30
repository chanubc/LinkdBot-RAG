# Retrieval Benchmark 요약 (2026-03-30)

## 1. 배경

이 브랜치는 제품 기능 브랜치가 아니라, retrieval 실험을 측정하고 정리하기 위한
script 전용 benchmark 브랜치다. `main`에 머지하는 것이 목적이 아니다.

이 문서의 목적은 다음 두 가지다.

- 이번 retrieval 실험에서 실제로 무엇을 측정했는지 기록한다.
- 다음 retrieval 실험이 같은 기준으로 다시 비교될 수 있도록 baseline을 남긴다.

이번 문서에서 비교한 상태는 아래 3개다.

- `before_branch`: `ef88190`
- `before_today`: `bc4a85f`
- `after_today`: 2026-03-30 기준 현재 working tree

## 2. 무엇을 측정했나

### 2-1. Benchmark accuracy harness

사용 스크립트:

- `scripts/eval_retriever.py`

측정 지표:

- Top1 Accuracy
- MRR
- P@5
- Recall@5
- 신규 케이스 Top1 hit 수

이 값은 synthetic benchmark 기준이다. 회귀 여부를 빠르게 확인하는 데는 유용하지만,
이 수치만으로 실제 사용자 검색 품질을 증명할 수는 없다.

### 2-2. Real-query sample accuracy

아래 3개 실제 쿼리를 고정하고, relevant URL을 수동 라벨링해서 비교했다.

- `하나 증권 채용`
- `채용공고 링크 가져와`
- `스타트업 취업 전략`

측정 지표:

- Top1 Accuracy
- MRR
- P@5
- Recall@5

이 방식은 synthetic benchmark보다 현실적이지만, 샘플 수가 너무 적어서
브랜치의 accuracy 차이를 강하게 증명하기에는 부족하다.

### 2-3. Real latency

사용 스크립트:

- `scripts/profile_retriever_latency.py --real --user 8362770686`

동일 브랜치에 대해 두 번 측정했다.

- 비교용 측정: `--repeats 5`
- 재확인 측정: `--repeats 10`

## 3. Benchmark Accuracy 비교

| 상태 | Top1 Accuracy | MRR | P@5 | Recall@5 | 신규 케이스 |
| --- | ---: | ---: | ---: | ---: | --- |
| `before_branch` (`ef88190`) | 0.8571 | 0.9286 | 0.2429 | 1.0000 | 4/4 |
| `before_today` (`bc4a85f`) | 0.8571 | 0.9286 | 0.2429 | 1.0000 | 4/4 |
| `after_today` (working tree) | 0.8571 | 0.9286 | 0.2429 | 1.0000 | 4/4 |

### 해석

이 3개 상태 사이에서는 benchmark accuracy가 변하지 않았다.

이건 예전 retrieval 문서와 모순이 아니다. 예전 문서는 `Dense` vs `PR#68` vs `Today`
같이 더 넓은 역사 비교를 보고 있었다. 반면 이번 비교는 같은 브랜치 계열 안에서
`브랜치 시작점`, `오늘 작업 전`, `오늘 작업 후`만 비교한 것이다.

즉, 이번 비교는 새로운 ranking 공식을 평가한 것이 아니라,
retrieval orchestration과 측정 경로를 다룬 비교에 가깝다. 그래서 accuracy가
평평하게 나오는 것이 자연스럽다.

## 4. Real-query Sample Accuracy 비교

Relevant URL은 실제 쿼리 benchmark를 돌릴 때 관찰한 결과를 기반으로 수동 라벨링했고,
3개 상태에 동일하게 고정했다.

| 상태 | Top1 Accuracy | MRR | P@5 | Recall@5 |
| --- | ---: | ---: | ---: | ---: |
| `before_branch` (`ef88190`) | 1.0000 | 1.0000 | 0.6000 | 1.0000 |
| `before_today` (`bc4a85f`) | 1.0000 | 1.0000 | 0.6000 | 1.0000 |
| `after_today` (working tree) | 1.0000 | 1.0000 | 0.6000 | 1.0000 |

### 해석

이 샘플에서도 accuracy 차이는 드러나지 않았다.

즉, 현재 3개 real query 셋은 분별력이 부족하다. smoke test로는 쓸 수 있지만,
이 브랜치가 accuracy를 의미 있게 바꿨는지 판단하기에는 약하다.

## 5. Real Latency 비교

### 5-1. 비교용 측정 (`--repeats 5`)

| 쿼리 | `before_branch` avg / p95 | `before_today` avg / p95 | `after_today` avg / p95 |
| --- | --- | --- | --- |
| `하나 증권 채용` | 362.75 / 430.91 ms | 478.39 / 947.15 ms | 540.94 / 1039.60 ms |
| `채용공고 링크 가져와` | 449.92 / 556.27 ms | 609.22 / 945.21 ms | 315.09 / 423.98 ms |
| `스타트업 취업 전략` | 715.71 / 776.46 ms | 769.64 / 1271.05 ms | 655.01 / 753.85 ms |

### 5-2. 재확인 측정 (`--repeats 10`, working tree only)

| 쿼리 | avg | p95 | 결과 수 |
| --- | ---: | ---: | ---: |
| `하나 증권 채용` | 450.14 ms | 1618.08 ms | 5 |
| `채용공고 링크 가져와` | 349.07 ms | 423.96 ms | 5 |
| `스타트업 취업 전략` | 682.11 ms | 788.22 ms | 4 |

### 해석

Latency는 깔끔한 승리가 아니라 혼합 결과다.

- `채용공고 링크 가져와`는 의미 있게 좋아졌다.
- `스타트업 취업 전략`은 소폭 좋아졌다.
- `하나 증권 채용`은 여전히 pre-branch baseline보다 느리고 tail도 거칠다.

그래서 요약은 이렇게 해야 한다.

- accuracy: 현재 benchmark 셋에서는 변화 없음
- latency: 일부 개선, 일부는 여전히 불안정

즉, 이 실험이 latency와 accuracy를 둘 다 개선했다고 말할 근거는 부족하다.

## 6. 왜 브랜치를 닫았는가

CTE-first retrieval 실험은 비용 대비 설득력 있는 품질 개선을 보여주지 못했다.

- benchmark accuracy가 현재 비교 기준에서는 평평했다.
- small real-query accuracy도 평평했다.
- latency는 일부 쿼리에서 좋아졌지만, 일부 쿼리에서는 더 나빴다.

그래서 이 실험은 제품 개선 브랜치라기보다, 학습과 측정 자산을 남긴 브랜치로
보는 것이 맞다.

## 7. 무엇을 남겼는가

retrieval 실험 자체는 유지하지 않았지만, benchmark 도구는 남길 가치가 있었다.

- `scripts/eval_retriever.py`
- `scripts/profile_retriever_latency.py`
- `tests/test_eval_retriever_script.py`

이 파일들은 다음 retrieval 실험에서 같은 질문을 반복 가능하게 만든다.

- accuracy가 움직였는가?
- latency가 움직였는가?
- 측정 경로 자체가 깨지지 않았는가?

## 8. 다음 추천 작업

retrieval accuracy를 다시 건드릴 일이 생기면, 예전 CTE-first 아이디어부터 다시
시작하지 않는 것이 좋다.

먼저 더 좋은 real labeled query set을 만드는 쪽이 맞다.

- 20개에서 30개 real query
- exact-heavy, fallback-heavy, variant, substring 케이스를 혼합
- relevant URL을 수동 라벨링

그 다음 이 브랜치의 benchmark 스크립트로 새 가설을 비교하면 된다.
