from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.external.notion_client import NotionClient


class NotionService:
    def __init__(self, user_repo: IUserRepository, notion: NotionClient) -> None:
        self._user_repo = user_repo
        self._notion = notion

    async def save(
        self,
        telegram_id: int,
        title: str,
        summary: str,
        category: str,
        keywords: list[str],
        url: str | None,
        memo: str | None = None,
    ) -> str:
        """Notion 데이터베이스에 항목 저장. 성공 시 페이지 URL 반환, 실패 시 빈 문자열."""
        token = await self._user_repo.get_decrypted_token(telegram_id)
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if not token or not user or not user.notion_database_id:
            return ""
        try:
            await self._notion.create_database_entry(
                access_token=token,
                database_id=user.notion_database_id,
                title=title,
                category=category,
                keywords=keywords,
                summary=summary,
                url=url,
                memo=memo,
            )
            db_id = user.notion_database_id.replace("-", "")
            return f"https://www.notion.so/{db_id}"
        except Exception:
            return ""

    async def get_db_url(self, telegram_id: int) -> str:
        """유저의 Notion 데이터베이스 URL 반환."""
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if not user or not user.notion_database_id:
            return ""
        db_id = user.notion_database_id.replace("-", "")
        return f"https://www.notion.so/{db_id}"
