import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.application.ports.notion_port import NotionPort
from app.application.ports.openai_llm_port import OpenAILLMPort
from app.application.ports.telegram_port import TelegramPort
from app.domain.repositories.i_user_repository import IUserRepository
from app.utils.text import split_chunks

logger = logging.getLogger(__name__)


class SaveMemoUseCase:
    def __init__(
        self,
        db: AsyncSession,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
        openai: OpenAILLMPort,
        telegram: TelegramPort,
        notion: NotionPort,
    ) -> None:
        self._db = db
        self._user_repo = user_repo
        self._link_repo = link_repo
        self._chunk_repo = chunk_repo
        self._openai = openai
        self._telegram = telegram
        self._notion = notion

    async def execute(self, telegram_id: int, memo: str) -> None:
        """메모 처리 파이프라인."""
        try:
            logger.info("[메모 처리 시작] 유저: %s, 내용: %s", telegram_id, memo)
            await self._user_repo.ensure_exists(telegram_id)
            link = await self._link_repo.save_memo(
                user_id=telegram_id,
                title=memo[:50],
                keywords=json.dumps([], ensure_ascii=False),
                memo=memo,
            )

            raw_chunks = split_chunks(memo)
            if raw_chunks:
                embeddings = await self._openai.embed(raw_chunks)
                await self._chunk_repo.save_chunks(link.id, list(zip(raw_chunks, embeddings)))

            await self._db.commit()

            notion_page_url = await self._save_to_notion(telegram_id, memo)

            msg = "✅ 메모 저장 완료!"
            if notion_page_url:
                user = await self._user_repo.get_by_telegram_id(telegram_id)
                if user and user.notion_database_id:
                    db_id = user.notion_database_id.replace("-", "")
                    msg += f"\n\n📓 Notion: https://www.notion.so/{db_id}"
            await self._telegram.send_message(telegram_id, msg)

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )

    async def _save_to_notion(self, telegram_id: int, memo: str) -> str:
        """Notion 저장. 성공 시 페이지 URL 반환, 실패 시 빈 문자열."""
        token = await self._user_repo.get_decrypted_token(telegram_id)
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if not token or not user or not user.notion_database_id:
            return ""
        try:
            await self._notion.create_database_entry(
                access_token=token,
                database_id=user.notion_database_id,
                title=memo[:50],
                category="Memo",
                keywords=[],
                summary="",
                url=None,
                memo=memo,
            )
            db_id = user.notion_database_id.replace("-", "")
            return f"https://www.notion.so/{db_id}"
        except Exception:
            return ""
