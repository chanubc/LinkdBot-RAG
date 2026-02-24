import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.ports.i_state_store import IStateStore
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.telegram_client import TelegramClient

logger = logging.getLogger(__name__)


class AuthService:
    def __init__(
        self,
        db: AsyncSession,
        notion: NotionClient,
        telegram: TelegramClient,
        user_repo: IUserRepository,
        state_store: IStateStore,
    ) -> None:
        self._db = db
        self._notion = notion
        self._telegram = telegram
        self._user_repo = user_repo
        self._state_store = state_store

    def create_login_url(self, telegram_id: int) -> str:
        """state 토큰을 생성하고 Notion OAuth 로그인 URL을 반환."""
        token = self._state_store.create(telegram_id)
        login_base = settings.NOTION_REDIRECT_URI.replace("/callback", "/login")
        return f"{login_base}?token={token}"

    def consume_state(self, token: str) -> int | None:
        """state 토큰을 소비하고 매핑된 telegram_id를 반환."""
        return self._state_store.consume(token)

    async def complete_notion_oauth(self, code: str, telegram_id: int) -> None:
        """Notion OAuth 완료 — 토큰 교환, DB 생성, 크리덴셜 저장, 알림 전송."""
        # 1. code → access_token 교환
        token_data = await self._notion.exchange_code(code)
        access_token: str = token_data["access_token"]

        # 2. 접근 가능한 첫 번째 페이지 하위에 LinkdBot DB 자동 생성
        page_id = await self._notion.get_accessible_page_id(access_token)
        database_id: str | None = None
        if page_id:
            try:
                database_id = await self._notion.create_database(access_token, page_id)
            except Exception:
                logger.exception("Notion DB 생성 실패 (telegram_id=%s)", telegram_id)

        # 3. 유저 크리덴셜 DB 저장
        await self._user_repo.upsert_notion_credentials(
            telegram_id=telegram_id,
            notion_access_token=access_token,
            notion_database_id=database_id,
        )
        await self._db.commit()

        # 4. 텔레그램 알림
        if database_id:
            await self._telegram.send_message(
                telegram_id,
                "✅ Notion 연동이 완료됐습니다!\n이제 링크를 전송하면 자동으로 저장됩니다.",
            )
        else:
            await self._telegram.send_message(
                telegram_id,
                "⚠️ Notion 계정 연동은 됐지만 데이터베이스를 생성하지 못했습니다.\n"
                "봇이 접근 가능한 Notion 페이지가 없습니다. "
                "Notion에서 페이지 접근 권한을 허용한 뒤 /start로 다시 시도해주세요.",
            )
