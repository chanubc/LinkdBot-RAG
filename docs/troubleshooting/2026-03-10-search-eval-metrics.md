# 검색 성능 정량 평가 (Before / After)

## 문제상황

한국어 Hybrid Search 개선 작업(PR #69) 후 검색 품질이 향상됐다고 주장할 수 있었지만,
구체적인 수치 근거가 없었다.

기존에는 A/B 비교 인프라나 평가 데이터셋이 없었기 때문에
"개선됐다"는 주장을 정량적으로 뒷받침할 수 없었다.

---

## 해결방안

오프라인 평가 스크립트(`scripts/eval_retriever.py`)를 작성해
Before (Dense-only) vs After (Keyword Rescoring) 방식을 동일한 후보군에 적용하고
표준 검색 지표로 비교했다.

**평가 설계:**
- 10개 쿼리 × 5개 후보 케이스 (한국어 도메인 다양화: 금융, 개발, AI, 인프라 등)
- 각 케이스에 정답 link_id(ground truth) 명시
- Before: `dense_score` 내림차순 정렬만 적용
- After: `_rescore_with_keywords()` 적용 (recall_k 확대 + keyword overlap 재점수화)

**측정 지표:**
- **P@5** (Precision at 5): 상위 5개 결과 중 정답 비율
- **MRR** (Mean Reciprocal Rank): 첫 정답이 몇 번째에 등장하는지의 역수 평균
- **NDCG@5**: 정답 순위에 log 가중치를 적용한 품질 지표

---

## 성과

10개 케이스 기준 결과:

| 지표 | Before (Dense-only) | After (Keyword Rescoring) | 개선율 |
|------|---------------------|--------------------------|--------|
| **P@5** | 0.2600 | 0.2600 | 0% |
| **MRR** | 0.3333 | 0.9500 | **+185%** |
| **NDCG@5** | 0.5084 | 0.9390 | **+85%** |
| **1위 정확도** | 1/10 (10%) | 9/10 (90%) | **+800%** |

**해석:**
- P@5가 동일한 이유: Before에서도 정답은 5위 안에 존재했음. 문제는 순위였음.
- MRR +185%: 사용자가 첫 번째 결과에서 정답을 만날 확률이 33% → 95%로 상승.
- 1위 개선 9/10: keyword overlap이 dense score만으로는 상위권에 오르지 못했던 정답 문서를 1위로 복구.

**1위에 오르지 못한 케이스 (1건):**
- 쿼리: "스타트업 투자 시리즈A" / content_source=`og` (keyword_weight=0.1로 낮음)
- og 소스는 keyword 가중치가 낮아 dense score가 높은 비관련 문서를 이기지 못함
- 한계이자 의도된 설계: og는 메타 정보만 있어 keyword 신뢰도가 낮으므로 가중치를 낮게 유지

---

## 평가 실행 방법

```bash
# mock 데이터로 실행
python scripts/eval_retriever.py

# 실제 DB 연결 (DATABASE_URL, OPENAI_API_KEY 환경변수 필요)
python scripts/eval_retriever.py --real --user {telegram_user_id}
```

실제 DB 평가 시 `scripts/eval_retriever.py` 내 `REAL_EVAL_QUERIES` 리스트에
쿼리와 정답 URL을 채워넣으면 동일한 지표를 실데이터 기준으로 측정할 수 있다.
