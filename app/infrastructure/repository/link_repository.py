from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_link_repository import ILinkRepository
from app.models.link import Link


class LinkRepository(ILinkRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def exists_by_user_and_url(self, user_id: int, url: str) -> bool:
        result = await self._db.execute(
            select(Link.id).where(Link.user_id == user_id, Link.url == url).limit(1)
        )
        return result.scalar_one_or_none() is not None

    async def save_link(
        self,
        user_id: int,
        url: str,
        title: str,
        summary: str,
        category: str,
        keywords: str,
        memo: str | None = None,
        content_source: str | None = None,
        summary_embedding: list[float] | None = None,
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
                content_source=content_source,
                summary_embedding=summary_embedding,
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

    async def get_unread_links(self, user_id: int, limit: int = 10) -> list[Link]:
        """읽지 않은 링크 목록 반환 (최신순)."""
        result = await self._db.execute(
            select(Link)
            .where(Link.user_id == user_id, Link.is_read.is_(False))
            .order_by(Link.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # --- Phase 3: Proactive Agent ---

    async def get_categories_by_period(
        self,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> list[str]:
        """기간 내 저장된 링크의 카테고리 목록 반환."""
        result = await self._db.execute(
            select(Link.category).where(
                Link.user_id == user_id,
                Link.created_at >= start,
                Link.created_at < end,
                Link.url.isnot(None),  # 메모 제외
            )
        )
        return list(result.scalars().all())

    async def get_summary_embeddings_by_period(
        self,
        user_id: int,
        start: datetime,
        end: datetime,
    ) -> list[list[float]]:
        """기간 내 저장된 링크의 summary_embedding 목록 반환 (None 제외)."""
        result = await self._db.execute(
            select(Link.summary_embedding).where(
                Link.user_id == user_id,
                Link.created_at >= start,
                Link.created_at < end,
                Link.summary_embedding.isnot(None),
            )
        )
        return [list(emb) for emb in result.scalars().all()]

    async def get_reactivation_candidates(
        self,
        user_id: int,
        older_than_days: int = 7,
        excluded_ids: list[int] | None = None,
    ) -> list[dict]:
        """재활성화 후보 링크 조회.

        조건:
        - is_read=False
        - created_at < now - older_than_days
        - summary_embedding IS NOT NULL
        - excluded_ids에 없는 링크
        """
        cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
        stmt = select(
            Link.id,
            Link.title,
            Link.url,
            Link.summary,
            Link.category,
            Link.summary_embedding,
            Link.created_at,
        ).where(
            Link.user_id == user_id,
            Link.is_read.is_(False),
            Link.created_at < cutoff,
            Link.summary_embedding.isnot(None),
        )
        if excluded_ids:
            stmt = stmt.where(Link.id.notin_(excluded_ids))

        result = await self._db.execute(stmt)
        rows = result.mappings().all()
        return [
            {
                "link_id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "summary": r["summary"],
                "category": r["category"],
                "summary_embedding": list(r["summary_embedding"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]

    async def get_all_summary_embeddings(
        self,
        user_id: int,
    ) -> list[list[float]]:
        """전체 링크의 summary_embedding 목록 반환 (None 제외, centroid 폴백용)."""
        result = await self._db.execute(
            select(Link.summary_embedding).where(
                Link.user_id == user_id,
                Link.summary_embedding.isnot(None),
            )
        )
        return [list(emb) for emb in result.scalars().all()]

    async def mark_as_read(self, link_id: int, user_id: int) -> bool:
        """링크 읽음 처리 (소유권 검증 포함). True = 성공, False = 링크 없음/타인 소유."""
        result = await self._db.execute(
            update(Link)
            .where(Link.id == link_id, Link.user_id == user_id)
            .values(is_read=True)
        )
        return (result.rowcount or 0) > 0

    # --- Phase 4: Dashboard ---

    async def get_all_links_with_metadata(
        self, user_id: int, limit: int = 500
    ) -> list[dict]:
        """전체 링크 메타데이터 조회 (최신순)."""
        result = await self._db.execute(
            select(
                Link.id,
                Link.title,
                Link.url,
                Link.category,
                Link.keywords,
                Link.is_read,
                Link.created_at,
                Link.summary,
            )
            .where(Link.user_id == user_id)
            .order_by(Link.created_at.desc())
            .limit(limit)
        )
        rows = result.mappings().all()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "url": r["url"],
                "category": r["category"],
                "keywords": r["keywords"],
                "is_read": r["is_read"],
                "created_at": r["created_at"].isoformat() if r["created_at"] else None,
                "summary": r["summary"],
            }
            for r in rows
        ]

    async def get_links_with_embeddings(
        self, user_id: int, limit: int = 300
    ) -> list[dict]:
        """summary_embedding이 있는 링크 조회 (PCA용)."""
        result = await self._db.execute(
            select(Link.id, Link.title, Link.category, Link.summary_embedding)
            .where(
                Link.user_id == user_id,
                Link.summary_embedding.isnot(None),
            )
            .order_by(Link.created_at.desc())
            .limit(limit)
        )
        rows = result.mappings().all()
        return [
            {
                "id": r["id"],
                "title": r["title"],
                "category": r["category"],
                "summary_embedding": list(r["summary_embedding"]),
            }
            for r in rows
        ]

    async def delete_link(self, link_id: int, user_id: int) -> bool:
        """링크 삭제 (소유권 검증 포함, CASCADE로 Chunk 자동 삭제). True = 성공, False = 링크 없음/타인 소유."""
        result = await self._db.execute(
            delete(Link).where(Link.id == link_id, Link.user_id == user_id)
        )
        return (result.rowcount or 0) > 0
