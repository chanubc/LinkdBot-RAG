"""app/domain/drift.py 단위 테스트."""
from app.domain.drift import calculate_category_distribution, calculate_drift


class TestCalculateCategoryDistribution:
    def test_empty_returns_empty(self):
        assert calculate_category_distribution([]) == {}

    def test_single_category(self):
        dist = calculate_category_distribution(["AI", "AI", "AI"])
        assert dist == {"AI": 1.0}

    def test_even_distribution(self):
        dist = calculate_category_distribution(["AI", "Dev"])
        assert dist["AI"] == 0.5
        assert dist["Dev"] == 0.5

    def test_proportions_sum_to_one(self):
        cats = ["AI", "Dev", "Career", "AI", "Business"]
        dist = calculate_category_distribution(cats)
        assert abs(sum(dist.values()) - 1.0) < 1e-9

    def test_counts_correctly(self):
        cats = ["AI", "AI", "Dev"]
        dist = calculate_category_distribution(cats)
        assert abs(dist["AI"] - 2 / 3) < 1e-9
        assert abs(dist["Dev"] - 1 / 3) < 1e-9


class TestCalculateDrift:
    def test_no_change_is_zero_tvd(self):
        cats = ["AI", "Dev", "AI", "Dev"]
        tvd, delta = calculate_drift(cats, cats)
        assert abs(tvd) < 1e-9
        for v in delta.values():
            assert abs(v) < 1e-9

    def test_complete_shift_is_max_tvd(self):
        current = ["AI", "AI"]
        past = ["Dev", "Dev"]
        tvd, delta = calculate_drift(current, past)
        # TVD = 0.5 * (|1 - 0| + |0 - 1|) = 1.0
        assert abs(tvd - 1.0) < 1e-9

    def test_delta_positive_for_new_category(self):
        current = ["AI", "AI"]
        past = ["Dev", "Dev"]
        _, delta = calculate_drift(current, past)
        assert delta["AI"] > 0
        assert delta["Dev"] < 0

    def test_partial_drift(self):
        current = ["AI", "AI", "Dev", "Dev"]
        past = ["AI", "Dev", "Dev", "Dev"]
        tvd, delta = calculate_drift(current, past)
        assert 0 < tvd < 1

    def test_empty_current(self):
        tvd, delta = calculate_drift([], ["AI", "Dev"])
        # current 비어있으면 모든 카테고리가 과거에만 존재 → TVD = 0.5
        assert abs(tvd - 0.5) < 1e-9

    def test_empty_both(self):
        tvd, delta = calculate_drift([], [])
        assert tvd == 0.0
        assert delta == {}
