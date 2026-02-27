"""app/domain/scoring.py 단위 테스트."""
from datetime import datetime, timedelta, timezone

import pytest

from app.domain.scoring import (
    calculate_forgetting_score,
    calculate_reactivation_score,
    compute_interest_centroid,
    cosine_similarity,
    select_reactivation_link,
)


class TestCosineSimilarity:
    def test_identical_vectors(self):
        v = [1.0, 0.0, 0.0]
        assert abs(cosine_similarity(v, v) - 1.0) < 1e-9

    def test_orthogonal_vectors(self):
        a = [1.0, 0.0]
        b = [0.0, 1.0]
        assert abs(cosine_similarity(a, b)) < 1e-9

    def test_opposite_vectors(self):
        a = [1.0, 0.0]
        b = [-1.0, 0.0]
        assert abs(cosine_similarity(a, b) + 1.0) < 1e-9

    def test_empty_vectors(self):
        assert cosine_similarity([], []) == 0.0

    def test_zero_vector(self):
        assert cosine_similarity([0.0, 0.0], [1.0, 0.0]) == 0.0

    def test_length_mismatch(self):
        assert cosine_similarity([1.0], [1.0, 2.0]) == 0.0


class TestComputeInterestCentroid:
    def test_empty_returns_none(self):
        assert compute_interest_centroid([]) is None

    def test_single_embedding(self):
        emb = [1.0, 2.0, 3.0]
        centroid = compute_interest_centroid([emb])
        assert centroid == emb

    def test_average_of_two(self):
        a = [1.0, 0.0]
        b = [3.0, 0.0]
        centroid = compute_interest_centroid([a, b])
        assert abs(centroid[0] - 2.0) < 1e-9
        assert abs(centroid[1]) < 1e-9

    def test_dimension_preserved(self):
        embs = [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0]]
        centroid = compute_interest_centroid(embs)
        assert len(centroid) == 3


class TestCalculateForgettingScore:
    def test_brand_new_link_is_near_zero(self):
        now = datetime.now(timezone.utc)
        score = calculate_forgetting_score(now)
        assert score < 0.1  # 방금 생성됐으면 망각 점수 낮음

    def test_old_link_approaches_one(self):
        old = datetime.now(timezone.utc) - timedelta(days=365)
        score = calculate_forgetting_score(old)
        assert score > 0.99

    def test_30_day_old_link(self):
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        score = calculate_forgetting_score(thirty_days_ago)
        # 1 - 1/(1+30) ≈ 0.967
        assert abs(score - (1 - 1 / 31)) < 0.01

    def test_naive_datetime_handled(self):
        naive = datetime.utcnow() - timedelta(days=10)
        score = calculate_forgetting_score(naive)
        assert 0 <= score <= 1


class TestCalculateReactivationScore:
    def test_score_in_range(self):
        centroid = [1.0, 0.0]
        link_emb = [1.0, 0.0]
        created_at = datetime.now(timezone.utc) - timedelta(days=30)
        score = calculate_reactivation_score(link_emb, centroid, created_at)
        assert 0.0 <= score <= 1.0

    def test_highly_relevant_old_link_scores_high(self):
        centroid = [1.0, 0.0]
        link_emb = [1.0, 0.0]  # 완전히 일치
        old_date = datetime.now(timezone.utc) - timedelta(days=365)
        score = calculate_reactivation_score(link_emb, centroid, old_date)
        # similarity ≈ 1 → 0~1 정규화 후 1.0, recency ≈ 1.0 → score ≈ 1.0
        assert score > 0.9

    def test_irrelevant_new_link_scores_low(self):
        centroid = [1.0, 0.0]
        link_emb = [0.0, 1.0]  # 직교 → 낮은 유사도
        new_date = datetime.now(timezone.utc)
        score = calculate_reactivation_score(link_emb, centroid, new_date)
        assert score < 0.5


class TestSelectReactivationLink:
    def _make_candidate(self, link_id: int, days_old: int, emb: list[float]) -> dict:
        return {
            "link_id": link_id,
            "summary_embedding": emb,
            "created_at": datetime.now(timezone.utc) - timedelta(days=days_old),
            "title": f"Link {link_id}",
        }

    def test_returns_none_for_empty(self):
        assert select_reactivation_link([], [1.0, 0.0]) is None

    def test_skips_candidates_without_embedding(self):
        candidates = [{"link_id": 1, "summary_embedding": None, "created_at": datetime.now(timezone.utc)}]
        result = select_reactivation_link(candidates, [1.0, 0.0])
        assert result is None

    def test_returns_best_candidate(self):
        centroid = [1.0, 0.0]
        c1 = self._make_candidate(1, days_old=1, emb=[0.0, 1.0])   # 유사도 낮음
        c2 = self._make_candidate(2, days_old=30, emb=[1.0, 0.0])  # 유사도 높음 + 오래됨
        result = select_reactivation_link([c1, c2], centroid)
        assert result is not None
        assert result["link_id"] == 2

    def test_result_has_score_key(self):
        centroid = [1.0, 0.0]
        c = self._make_candidate(1, days_old=10, emb=[1.0, 0.0])
        result = select_reactivation_link([c], centroid)
        assert "score" in result
        assert 0.0 <= result["score"] <= 1.0
