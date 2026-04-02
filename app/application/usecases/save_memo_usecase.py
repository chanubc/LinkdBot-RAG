import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.ports.notion_port import NotionPort
from app.application.ports.telegram_port import TelegramPort
from app.core.logger import logger
from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.utils.text import split_chunks


class SaveMemoUseCase:
    def __init__(
        self,
        db: AsyncSession,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
        openai: AIAnalysisPort,
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
        try:
            await self._telegram.send_message(telegram_id, "📝 메모를 저장하는 중입니다...")

            logger.info(f"[메모 처리 시작] 유저: {telegram_id}, 내용: {memo}")
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
                msg += f"\n\n📓 Notion: {notion_page_url}"
            await self._telegram.send_message(telegram_id, msg)

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )

    async def _save_to_notion(self, telegram_id: int, memo: str) -> str:
        token = await self._user_repo.get_decrypted_token(telegram_id)
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if not token or not user or not user.notion_database_id:
            return ""
        try:
            return await self._notion.create_database_entry(
                access_token=token,
                database_id=user.notion_database_id,
                title=memo[:50],
                category="Memo",
                keywords=[],
                description="",
                url=None,
                memo=memo,
            )
        except Exception as exc:
            logger.exception(
                f"Notion memo save failed (telegram_id={telegram_id}, database_id={user.notion_database_id}): {exc}"
            )
            return ""
