import json

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.repository.user_repository import UserRepository


def _split_chunks(text: str, size: int = 800) -> list[str]:
    """텍스트를 500~1000자 단위 청크로 분할."""
    words = text.split()
    chunks: list[str] = []
    buf: list[str] = []
    length = 0
    for word in words:
        wl = len(word) + 1
        if length + wl > size and buf:
            chunks.append(" ".join(buf))
            buf, length = [word], wl
        else:
            buf.append(word)
            length += wl
    if buf:
        chunks.append(" ".join(buf))
    return chunks


class LinkService:
    def __init__(
        self,
        db: AsyncSession,
        openai: OpenAIClient,
        notion: NotionClient,
        telegram: TelegramClient,
    ) -> None:
        self._db = db
        self._openai = openai
        self._notion = notion
        self._telegram = telegram

    # ── Public ──────────────────────────────────────────────────────────────

    async def process_link(self, telegram_id: int, url: str, memo: str | None = None) -> None:
        """링크 처리 파이프라인 (BackgroundTask로 비동기 실행)."""
        await self._telegram.send_message(telegram_id, "🔍 처리 중...")
        try:
            # 1. Scrape
            content = await self._scrape(url)
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
            user_repo = UserRepository(self._db)
            link_repo = LinkRepository(self._db)
            await user_repo.ensure_exists(telegram_id)
            link = await link_repo.save_link(
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
            raw_chunks = _split_chunks(content)
            if raw_chunks:
                embeddings = await self._openai.embed(raw_chunks)
                await link_repo.save_chunks(link.id, list(zip(raw_chunks, embeddings)))

            # 5. Notion 저장 (optional)
            notion_url = await self._save_to_notion(
                telegram_id, title, summary, category, keywords, url
            )

            # 6. 완료 알림
            await self._telegram.send_message(
                telegram_id,
                _build_done_message(title, category, keywords, summary, notion_url),
            )

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )

    async def process_memo(self, telegram_id: int, memo: str) -> None:
        """메모 처리 파이프라인 (URL 없는 텍스트)."""
        await self._telegram.send_message(telegram_id, "📝 메모 저장 중...")
        try:
            # 1. Analyze
            analysis = await self._openai.analyze_content(memo)
            title: str = analysis.get("title") or memo[:50]
            summary: str = analysis.get("summary", "")
            category: str = analysis.get("category", "Other")
            keywords: list[str] = analysis.get("keywords", [])
            keywords_json = json.dumps(keywords, ensure_ascii=False)

            # 2. DB 저장
            user_repo = UserRepository(self._db)
            link_repo = LinkRepository(self._db)
            await user_repo.ensure_exists(telegram_id)
            link = await link_repo.save_link(
                user_id=telegram_id,
                url=None,
                title=title,
                summary=summary,
                category=category,
                keywords=keywords_json,
                memo=memo,
            )
            if link is None:
                await self._telegram.send_message(telegram_id, "⚠️ 이미 저장된 메모입니다.")
                return

            # 3. Embed & chunk 저장
            raw_chunks = _split_chunks(memo)
            if raw_chunks:
                embeddings = await self._openai.embed(raw_chunks)
                await link_repo.save_chunks(link.id, list(zip(raw_chunks, embeddings)))

            # 4. Notion 저장 (optional)
            notion_url = await self._save_to_notion(
                telegram_id, title, summary, category, keywords, url=None
            )

            # 5. 완료 알림
            await self._telegram.send_message(
                telegram_id,
                _build_done_message(title, category, keywords, summary, notion_url),
            )

        except Exception as exc:
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )

    async def search(
        self, telegram_id: int, query: str, top_k: int = 5
    ) -> list[dict]:
        """시맨틱 검색."""
        link_repo = LinkRepository(self._db)
        [embedding] = await self._openai.embed([query])
        return await link_repo.search_similar(telegram_id, embedding, top_k)

    # ── Private ─────────────────────────────────────────────────────────────

    async def _scrape(self, url: str) -> str:
        """OG 메타태그 기반 콘텐츠 추출."""
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LinkdBot/1.0)"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        og_title = soup.find("meta", property="og:title")
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        title_tag = soup.find("title")

        title = (
            (og_title.get("content") if og_title else None)
            or (title_tag.string if title_tag else None)
            or ""
        )
        description = (
            (og_desc.get("content") if og_desc else None)
            or (meta_desc.get("content") if meta_desc else None)
            or ""
        )

        content = f"{title}\n\n{description}".strip()
        if not content:
            raise ValueError("페이지에서 콘텐츠를 추출할 수 없습니다.")
        return content

    async def _save_to_notion(
        self,
        telegram_id: int,
        title: str,
        summary: str,
        category: str,
        keywords: list[str],
        url: str | None,
    ) -> str:
        user_repo = UserRepository(self._db)
        token = await user_repo.get_decrypted_token(telegram_id)
        user = await user_repo.get_by_telegram_id(telegram_id)
        if not token or not user or not user.notion_page_id:
            return ""
        try:
            return await self._notion.create_page(
                access_token=token,
                parent_page_id=user.notion_page_id,
                title=title,
                summary=summary,
                category=category,
                keywords=keywords,
                url=url,
            )
        except Exception:
            return ""


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
