import html
import json
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.ports.notion_port import NotionPort
from app.application.ports.scraper_port import ScraperPort
from app.application.ports.telegram_port import TelegramPort
from app.domain.repositories.i_user_repository import IUserRepository
from app.utils.text import split_chunks, split_markdown

logger = logging.getLogger(__name__)


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
        try:
            # 0. 즉시 피드백 (사용자에게 처리 시작 알림)
            await self._telegram.send_message(telegram_id, "🔗 링크를 저장하는 중이에요...")

            # 1. Scrape
            content, content_source = await self._scraper.scrape(url)
            if memo:
                content = f"{content}\n\n{memo}"
            await self._telegram.send_message(telegram_id, "✅ 링크 내용 스크랩이 완료되었어요.")

            # 2. Analyze
            await self._telegram.send_message(telegram_id, "🤖 AI가 내용을 분석하고 있어요...")
            analysis = await self._openai.analyze_content(content)
            title: str = analysis.title or url
            summary: str = analysis.summary
            category: str = analysis.category
            keywords: list[str] = analysis.keywords
            keywords_json = json.dumps(keywords, ensure_ascii=False)

            # 2-1. Summary 임베딩 생성 (Drift/Reactivation 계산용)
            if summary:
                [summary_embedding] = await self._openai.embed([summary])
            else:
                summary_embedding = None

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

            # 4. Embed & chunk 저장 (Jina 콘텐츠면 Markdown 분할, 아니면 단어 분할)
            if content_source == "jina":
                raw_chunks = split_markdown(content)
            else:
                raw_chunks = split_chunks(content)
            if raw_chunks:
                embeddings = await self._openai.embed(raw_chunks)
                await self._chunk_repo.save_chunks(link.id, list(zip(raw_chunks, embeddings)))

            # 5. 단일 커밋
            await self._db.commit()

            # 6. Notion 저장 (optional, non-fatal)
            notion_url = await self._save_to_notion(
                telegram_id, title, summary, category, keywords, url, memo
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
        category: str,
        keywords: list[str],
        url: str | None,
        memo: str | None,
    ) -> str:
        """Notion 저장. 성공 시 DB URL 반환, 실패 시 빈 문자열."""
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
