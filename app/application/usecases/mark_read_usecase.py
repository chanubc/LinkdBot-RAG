from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_link_repository import ILinkRepository


class MarkReadUseCase:
    """읽음 처리 콜백 쓰기 흐름 조율."""

    def __init__(
        self,
        db: AsyncSession,
        link_repo: ILinkRepository,
    ) -> None:
        self._db = db
        self._link_repo = link_repo

    async def execute(self, telegram_id: int, link_id: int) -> bool:
        """읽음 처리 후 성공 시 커밋."""
        success = await self._link_repo.mark_as_read(link_id, telegram_id)
        if success:
            await self._db.commit()
        return success
