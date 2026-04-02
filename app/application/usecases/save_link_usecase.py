import html
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.ports.notion_port import NotionPort
from app.application.ports.scraper_port import ScraperPort
from app.application.ports.telegram_port import TelegramPort
from app.core.logger import logger
from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.utils.text import split_markdown
from app.utils.url import normalize_url


class SaveLinkUseCase:
    def __init__(
        self,
        db: AsyncSession,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        chunk_repo: IChunkRepository,
        openai: AIAnalysisPort,
        scraper: ScraperPort,
        telegram: TelegramPort,
        notion: NotionPort,
    ) -> None:
        self._db = db
        self._user_repo = user_repo
        self._link_repo = link_repo
        self._chunk_repo = chunk_repo
        self._openai = openai
        self._scraper = scraper
        self._telegram = telegram
        self._notion = notion

    async def execute(self, telegram_id: int, url: str, memo: str | None = None) -> None:
        url = normalize_url(url)
        try:
            if await self._link_repo.exists_by_user_and_url(telegram_id, url):
                await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 링크입니다.")
                return

            await self._telegram.send_message(telegram_id, "🔗 링크 내용 스크랩을 시작했어요.")

            scraped_content, content_source, og_description, og_title = _normalize_scrape_result(
                await self._scraper.scrape(url)
            )
            content = scraped_content
            if memo:
                content = f"{content}\n\n{memo}"
            await self._telegram.send_message(telegram_id, "✅ 링크 내용 스크랩이 완료되었어요.")

            await self._telegram.send_message(telegram_id, "🤖 AI가 내용을 분석하고 있어요...")
            analysis = await self._openai.analyze_content(content)
            title: str = og_title or analysis.title or url
            description: str = og_description
            category: str = analysis.category
            keywords: list[str] = analysis.keywords
            keywords_json = json.dumps(keywords, ensure_ascii=False)

            summary: str = analysis.semantic_summary or description
            ai_summary: str = summary

            if content_source == "jina":
                raw_chunks = split_markdown(content)
            else:
                raw_chunks = []

            embedding_inputs: list[str] = []
            has_summary_embedding = bool(summary)
            if has_summary_embedding:
                embedding_inputs.append(summary)
            embedding_inputs.extend(raw_chunks)

            summary_embedding: list[float] | None = None
            chunk_embeddings: list[list[float]] = []
            if embedding_inputs:
                batched_embeddings = await self._openai.embed(embedding_inputs)
                if len(batched_embeddings) != len(embedding_inputs):
                    raise ValueError("Embedding count mismatch")
                chunk_start_idx = 0
                if has_summary_embedding:
                    summary_embedding = batched_embeddings[0]
                    chunk_start_idx = 1
                chunk_embeddings = batched_embeddings[chunk_start_idx:]

            await self._user_repo.ensure_exists(telegram_id)
            link = await self._link_repo.save_link(
                user_id=telegram_id,
                url=url,
                title=title,
                summary=summary,
                category=category,
                keywords=keywords_json,
                memo=memo,
                content_source=content_source,
                summary_embedding=summary_embedding,
            )
            if link is None:
                await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 링크입니다.")
                return

            if raw_chunks and chunk_embeddings:
                await self._chunk_repo.save_chunks(link.id, list(zip(raw_chunks, chunk_embeddings)))

            await self._db.commit()

            notion_url = await self._save_to_notion(
                telegram_id=telegram_id,
                title=title,
                description=description,
                ai_summary=ai_summary,
                category=category,
                keywords=keywords,
                url=url,
                memo=memo,
            )

            await self._telegram.send_link_saved_message(
                chat_id=telegram_id,
                text=_build_done_message(title, category, keywords, summary),
                notion_url=notion_url or None,
            )

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {html.escape(str(exc)[:200])}"
            )

    async def _save_to_notion(
        self,
        telegram_id: int,
        title: str,
        description: str,
        ai_summary: str,
        category: str,
        keywords: list[str],
        url: str | None,
        memo: str | None,
    ) -> str:
        token = await self._user_repo.get_decrypted_token(telegram_id)
        user = await self._user_repo.get_by_telegram_id(telegram_id)
        if not token or not user or not user.notion_database_id:
            return ""
        try:
            return await self._notion.create_database_entry(
                access_token=token,
                database_id=user.notion_database_id,
                title=title,
                category=category,
                keywords=keywords,
                description=description,
                ai_summary=ai_summary,
                url=url,
                memo=memo,
            )
        except Exception as exc:
            logger.exception(
                f"Notion save failed (telegram_id={telegram_id}, database_id={user.notion_database_id}, url={url}): {exc}"
            )
            await self._telegram.send_message(
                telegram_id, f"⚠️ Notion 저장 실패: {html.escape(str(exc)[:200])}"
            )
            return ""


def _normalize_scrape_result(scrape_result: tuple[str, ...]) -> tuple[str, str, str, str]:
    if len(scrape_result) == 4:
        content, content_source, og_description, og_title = scrape_result
        return content, content_source, og_description, og_title
    if len(scrape_result) == 3:
        content, content_source, og_description = scrape_result
        return content, content_source, og_description, ""
    if len(scrape_result) == 2:
        content, content_source = scrape_result
        return content, content_source, "", ""
    raise ValueError("Unexpected scrape result format")


def _build_done_message(
    title: str,
    category: str,
    keywords: list[str],
    summary: str,
) -> str:
    return (
        f"✅ 저장 완료!\n\n"
        f"📌 <b>{html.escape(title)}</b>\n"
        f"📂 {html.escape(category)}  |  🔑 {html.escape(', '.join(keywords))}\n\n"
        f"📝 {html.escape(summary)}"
    )
