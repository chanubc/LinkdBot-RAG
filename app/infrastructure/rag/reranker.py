class SimpleReranker:
    """similarity 기준 정렬. Phase 3+에서 교차 인코더 등으로 확장."""

    def rerank(self, results: list[dict], top_k: int) -> list[dict]:
        """similarity 내림차순 정렬 후 top_k 반환."""
        return sorted(results, key=lambda r: r.get("similarity", 0), reverse=True)[:top_k]
