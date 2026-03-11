from datetime import datetime, time, timedelta, timezone

from app.domain.repositories.i_link_repository import ILinkRepository


class RecallMemoUseCase:
    def __init__(self, link_repo: ILinkRepository) -> None:
        self._link_repo = link_repo

    async def execute(
        self,
        telegram_id: int,
        query: str | None = None,
        time_filter: str | None = None,
        limit: int = 5,
    ) -> list[dict]:
        start, end = self._to_period(time_filter)
        memos = await self._link_repo.get_memos_by_period(
            user_id=telegram_id,
            start=start,
            end=end,
            query=query,
            limit=limit,
        )
        return [
            {
                "title": memo.title,
                "url": None,
                "similarity": 1.0,
                "created_at": memo.created_at.isoformat() if memo.created_at else None,
                "memo": memo.memo,
            }
            for memo in memos
        ]

    @staticmethod
    def _to_period(time_filter: str | None) -> tuple[datetime, datetime]:
        now = datetime.now(timezone.utc)
        today_start = datetime.combine(now.date(), time.min, tzinfo=timezone.utc)

        if time_filter == "today":
            return today_start, now
        if time_filter == "yesterday":
            return today_start - timedelta(days=1), today_start
        if time_filter == "last_7_days":
            return now - timedelta(days=7), now
        # default: recent
        return now - timedelta(days=30), now
