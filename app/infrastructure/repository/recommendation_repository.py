from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_recommendation_repository import IRecommendationRepository
from app.models.recommendation import Recommendation


class RecommendationRepository(IRecommendationRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def record(self, link_id: int, user_id: int) -> None:
        """추천 기록 저장."""
        self._db.add(Recommendation(link_id=link_id, user_id=user_id))

    async def get_recently_recommended_link_ids(
        self,
        user_id: int,
        within_days: int = 14,
    ) -> list[int]:
        """최근 N일 이내 추천된 link_id 목록 반환."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=within_days)
        result = await self._db.execute(
            select(Recommendation.link_id).where(
                Recommendation.user_id == user_id,
                Recommendation.recommended_at >= cutoff,
            )
        )
        return list(result.scalars().all())
