from abc import ABC, abstractmethod
from datetime import datetime


class IRecommendationRepository(ABC):
    """추천 이력 관리 Repository Interface."""

    @abstractmethod
    async def record(self, link_id: int, user_id: int) -> None:
        """추천 기록 저장."""
        ...

    @abstractmethod
    async def get_recently_recommended_link_ids(
        self,
        user_id: int,
        within_days: int = 14,
    ) -> list[int]:
        """최근 N일 이내 이미 추천된 link_id 목록 반환 (중복 추천 방지용)."""
        ...
