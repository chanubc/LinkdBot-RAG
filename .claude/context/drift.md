# 📊 Interest Drift

사용자의 관심사가 얼마나 이동했는지를 카테고리 비중 변화로 수치화한 지표.

## Formula

```
D(c) = P_current(c) - P_past(c)
```

Where:
- `P_current(c)` = 최근 7일 동안 저장된 링크 중 카테고리 c의 비중
- `P_past(c)` = 과거 30일 동안 저장된 링크 중 카테고리 c의 비중

Overall Drift = Total Variation Distance:
```
TVD = 0.5 × Σ|P_current(c) - P_past(c)|
```

## 기간 선택 근거

- **최근 7일**: "이번 주" 관심사 — 주간 리포트 주기와 일치
- **기준 30일**: 안정적인 기준선 — 단기 노이즈를 걸러냄
- 7 vs 7 비교는 주간 노이즈에 너무 민감하므로 채택하지 않음

## 주의사항

카테고리는 반드시 고정 목록에서만 선택되어야 함. LLM 자유 생성 허용 시 'AI'와 'Artificial Intelligence'가 별개 카테고리로 취급되어 Drift 계산이 무의미해짐.

```python
ALLOWED_CATEGORIES = ["AI", "Dev", "Career", "Business", "Design", "Other"]
```

## Usage

주간 리포트(Phase 3) 시 실행. 가장 큰 D(c) 값을 가진 카테고리를 브리핑에 포함.
Implemented in `app/domain/drift.py`.
