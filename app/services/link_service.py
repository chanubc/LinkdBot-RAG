import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.text import split_chunks
from app.infrastructure.external.scraper_client import ScraperClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.services.notion_service import NotionService

logger = logging.getLogger(__name__)


class LinkService:
    def __init__(
        self,
        db: AsyncSession,
        openai: OpenAIClient,
        scraper: ScraperClient,
        notion_svc: NotionService,
        telegram: TelegramClient,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
    ) -> None:
        self._db = db
        self._openai = openai
        self._scraper = scraper
        self._notion_svc = notion_svc
        self._telegram = telegram
        self._user_repo = user_repo
        self._link_repo = link_repo
        self._chunk_repo = chunk_repo

    async def process_link(self, telegram_id: int, url: str, memo: str | None = None) -> None:
        """링크 처리 파이프라인 (BackgroundTask로 비동기 실행)."""
        await self._telegram.send_message(telegram_id, "🔍 처리 중...")
        try:
            # 1. Scrape
            content = await self._scraper.scrape(url)
            if memo:
                content = f"{content}\n\n{memo}"

            # 2. Analyze
            analysis = await self._openai.analyze_content(content)
            title: str = analysis.get("title") or url
            summary: str = analysis.get("summary", "")
            category: str = analysis.get("category", "Other")
            keywords: list[str] = analysis.get("keywords", [])
            keywords_json = json.dumps(keywords, ensure_ascii=False)

            # 3. DB 저장
            await self._user_repo.ensure_exists(telegram_id)
            link = await self._link_repo.save_link(
                user_id=telegram_id,
                url=url,
                title=title,
                summary=summary,
                category=category,
                keywords=keywords_json,
                memo=memo,
            )
            if link is None:
                await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 링크입니다.")
                return

            # 4. Embed & chunk 저장
            raw_chunks = split_chunks(content)
            if raw_chunks:
                embeddings = await self._openai.embed(raw_chunks)
                await self._chunk_repo.save_chunks(link.id, list(zip(raw_chunks, embeddings)))

            # 5. 단일 커밋 (ensure_exists + save_link + save_chunks를 하나의 트랜잭션으로 확정)
            await self._db.commit()

            # 6. Notion 저장 (optional, DB 커밋 이후 외부 API 호출)
            notion_url = await self._notion_svc.save(
                telegram_id, title, summary, category, keywords, url, memo
            )

            # 7. 완료 알림
            await self._telegram.send_message(
                telegram_id,
                _build_done_message(title, category, keywords, summary, notion_url),
            )

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )


def _build_done_message(
    title: str,
    category: str,
    keywords: list[str],
    summary: str,
    notion_url: str,
) -> str:
    msg = (
        f"✅ 저장 완료!\n\n"
        f"📌 <b>{title}</b>\n"
        f"📂 {category}  |  🔑 {', '.join(keywords)}\n\n"
        f"📝 {summary}"
    )
    if notion_url:
        msg += f"\n\n📓 Notion: {notion_url}"
    return msg
