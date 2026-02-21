# 🔁 Reactivation Score

아직 읽지 않은 링크 중 "지금 다시 꺼내볼 가치"가 가장 높은 링크를 선정하는 점수.

## Formula

```
Score = (Similarity × 0.6) + (Recency × 0.4)
```

사전 조건: `is_read=False` 링크만 대상 (Unread는 필터 조건으로 처리, 가중치 불필요)

## Variables

**Similarity (가중치 0.6)**
- 현재 관심사 벡터와 링크 embedding의 코사인 유사도
- **현재 관심사 벡터** = 최근 7일 저장된 링크들의 `chunks.embedding` 평균(centroid)
- 최근 7일 저장 링크가 없으면 전체 링크의 centroid로 폴백

**Recency (가중치 0.4)**
- 오래된 링크일수록 높은 점수 (망각된 지식 재활성화 목적)
- `recency = 1 - (1 / (1 + days_since_created))` — 오래될수록 1에 수렴

## Usage

주간 리포트(Phase 3) 시 실행. `is_read=False` 전체 링크 중 Score 1위 링크를 텔레그램으로 푸시.
Implemented in `app/domain/scoring.py`.
