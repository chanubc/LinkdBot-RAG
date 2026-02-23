import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.text import split_chunks
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.services.notion_service import NotionService

logger = logging.getLogger(__name__)


class MemoService:
    def __init__(
        self,
        db: AsyncSession,
        openai: OpenAIClient,
        notion_svc: NotionService,
        telegram: TelegramClient,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
    ) -> None:
        self._db = db
        self._openai = openai
        self._notion_svc = notion_svc
        self._telegram = telegram
        self._user_repo = user_repo
        self._link_repo = link_repo
        self._chunk_repo = chunk_repo

    async def process_memo(self, telegram_id: int, memo: str) -> None:
        """메모 처리 파이프라인 (URL 없는 텍스트, AI 분석 없이 저장)."""
        await self._telegram.send_message(telegram_id, "📝 메모 저장 중...")
        try:
            # 1. DB 저장 (AI 분석 없이)
            logger.info(f"[메모 처리 시작fdfdfdffd] 유저: {telegram_id}, 내용: {memo}")
            await self._user_repo.ensure_exists(telegram_id)
            link = await self._link_repo.save_memo(
                user_id=telegram_id,
                title=memo[:50],
                keywords=json.dumps([], ensure_ascii=False),
                memo=memo,
            )

            # 2. Embed & chunk 저장 (검색을 위해 유지)
            raw_chunks = split_chunks(memo)
            if raw_chunks:
                embeddings = await self._openai.embed(raw_chunks)
                await self._chunk_repo.save_chunks(link.id, list(zip(raw_chunks, embeddings)))

            # 3. 단일 커밋 (ensure_exists + save_memo + save_chunks를 하나의 트랜잭션으로 확정)
            await self._db.commit()

            # 4. Notion 저장 (optional, DB 커밋 이후 외부 API 호출)
            notion_page_url = await self._notion_svc.save(
                telegram_id, memo[:50], "", "Memo", [], url=None, memo=memo
            )

            # 5. 완료 알림
            msg = "✅ 메모 저장 완료!"
            if notion_page_url:
                notion_db_url = await self._notion_svc.get_db_url(telegram_id)
                msg += f"\n\n📓 Notion: {notion_db_url}"
            await self._telegram.send_message(telegram_id, msg)

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )
