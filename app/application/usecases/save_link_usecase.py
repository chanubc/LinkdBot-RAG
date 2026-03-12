import html
import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.ports.notion_port import NotionPort
from app.application.ports.scraper_port import ScraperPort
from app.application.ports.telegram_port import TelegramPort
from app.domain.repositories.i_user_repository import IUserRepository
from app.utils.text import split_chunks, split_markdown
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
        """링크 처리 파이프라인 (BackgroundTask로 비동기 실행).

        웹훅은 이 함수 호출 즉시 응답하므로, 모든 사용자 피드백은 이 함수 내에서 관리됨.
        """
        url = normalize_url(url)
        try:
            if await self._link_repo.exists_by_user_and_url(telegram_id, url):
                await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 링크입니다.")
                return

            # 0. 즉시 피드백 (사용자에게 처리 시작 알림)
            await self._telegram.send_message(telegram_id, "🔗 링크를 저장하는 중이에요...")

            # 1. Scrape
            scraped_content, content_source, og_description = _normalize_scrape_result(
                await self._scraper.scrape(url)
            )
            content = scraped_content
            if memo:
                content = f"{content}\n\n{memo}"
            await self._telegram.send_message(telegram_id, "✅ 링크 내용 스크랩이 완료되었어요.")

            # 2. Analyze
            await self._telegram.send_message(telegram_id, "🤖 AI가 내용을 분석하고 있어요...")
            analysis = await self._openai.analyze_content(content)
            title: str = analysis.title or url
            summary: str = og_description or analysis.summary
            category: str = analysis.category
            keywords: list[str] = analysis.keywords
            keywords_json = json.dumps(keywords, ensure_ascii=False)

            # 2-1. Summary + chunks 임베딩을 1회 호출로 배치 처리
            if content_source == "jina":
                raw_chunks = split_markdown(content)
            else:
                raw_chunks = split_chunks(content)

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
                content_source=content_source,
                summary_embedding=summary_embedding,
            )
            if link is None:
                await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 링크입니다.")
                return

            # 4. chunk 저장
            if raw_chunks and chunk_embeddings:
                await self._chunk_repo.save_chunks(link.id, list(zip(raw_chunks, chunk_embeddings)))

            # 5. 단일 커밋
            await self._db.commit()

            # 6. Notion 저장 (optional, non-fatal)
            notion_url = await self._save_to_notion(
                telegram_id=telegram_id,
                title=title,
                summary=summary,
                content=content,
                category=category,
                keywords=keywords,
                url=url,
                memo=memo,
            )

            # 7. 완료 알림
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
        summary: str,
        content: str,
        category: str,
        keywords: list[str],
        url: str | None,
        memo: str | None,
    ) -> str:
        """Notion 저장. 성공 시 child page URL 반환, 실패 시 빈 문자열."""
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
                summary=summary,
                content=content,
                url=url,
                memo=memo,
            )
        except Exception:
            return ""


def _normalize_scrape_result(scrape_result: tuple[str, ...]) -> tuple[str, str, str]:
    if len(scrape_result) == 3:
        content, content_source, og_description = scrape_result
        return content, content_source, og_description
    if len(scrape_result) == 2:
        content, content_source = scrape_result
        return content, content_source, ""
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
