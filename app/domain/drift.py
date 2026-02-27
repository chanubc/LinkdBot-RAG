"""Interest Drift 계산 — 순수 함수 (외부 의존성 없음).

D(c) = P_current(c) - P_past(c)
TVD  = 0.5 * Σ|P_current(c) - P_past(c)|
"""
from __future__ import annotations

ALLOWED_CATEGORIES = ["AI", "Dev", "Career", "Business", "Design", "Science", "Other"]


def calculate_category_distribution(categories: list[str]) -> dict[str, float]:
    """카테고리 목록 → 각 카테고리의 비중(0~1) 딕셔너리.

    Args:
        categories: 링크 카테고리 문자열 목록.

    Returns:
        {category: proportion} — 목록이 비어있으면 빈 dict 반환.
    """
    if not categories:
        return {}
    total = len(categories)
    dist: dict[str, float] = {}
    for c in categories:
        dist[c] = dist.get(c, 0) + 1
    return {c: count / total for c, count in dist.items()}


def calculate_drift(
    current_categories: list[str],
    past_categories: list[str],
) -> tuple[float, dict[str, float]]:
    """관심사 변화 수치화.

    Args:
        current_categories: 최근 7일 저장된 링크의 카테고리 목록.
        past_categories:    과거 30일 저장된 링크의 카테고리 목록.

    Returns:
        (tvd, delta_per_category)
        tvd: Total Variation Distance (0~1). 값이 클수록 관심사 이동 큼.
        delta_per_category: {category: D(c)} — 양수면 관심 증가, 음수면 감소.
    """
    p_current = calculate_category_distribution(current_categories)
    p_past = calculate_category_distribution(past_categories)

    all_cats = set(p_current) | set(p_past)
    delta: dict[str, float] = {
        c: p_current.get(c, 0.0) - p_past.get(c, 0.0) for c in all_cats
    }
    tvd = 0.5 * sum(abs(d) for d in delta.values())
    return tvd, delta
