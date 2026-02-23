from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_link_repository import ILinkRepository
from app.models.link import Link


class LinkRepository(ILinkRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def save_link(
        self,
        user_id: int,
        url: str,
        title: str,
        summary: str,
        category: str,
        keywords: str,
        memo: str | None = None,
    ) -> Link | None:
        """URL 링크 저장. 중복(user_id + url) 시 None 반환."""
        stmt = (
            insert(Link)
            .values(
                user_id=user_id,
                url=url,
                title=title,
                summary=summary,
                category=category,
                keywords=keywords,
                memo=memo,
            )
            .on_conflict_do_nothing(constraint="uq_user_url")
            .returning(Link)
        )
        result = await self._db.execute(stmt)
        return result.scalar_one_or_none()

    async def save_memo(
        self,
        user_id: int,
        title: str,
        keywords: str,
        memo: str,
    ) -> Link:
        """메모 저장. 중복 체크 없이 항상 저장."""
        link = Link(
            user_id=user_id,
            url=None,
            title=title,
            summary="",
            category="Memo",
            keywords=keywords,
            memo=memo,
        )
        self._db.add(link)
        await self._db.flush()
        await self._db.refresh(link)
        return link

