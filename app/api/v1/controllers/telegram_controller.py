import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

from fastapi import BackgroundTasks

from app.config import settings
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.infrastructure.state_store import create as create_state_token
from app.services.link_service import LinkService

logger = logging.getLogger(__name__)


# ── Handler Context ──────────────────────────────────────────────────────────

@dataclass
class HandlerCtx:
    telegram_id: int
    text: str
    message: dict
    background_tasks: BackgroundTasks
    link_service: LinkService
    telegram: TelegramClient
    user_repo: UserRepository


# ── Individual Handlers ──────────────────────────────────────────────────────

async def handle_callback(callback: dict, telegram: TelegramClient) -> None:
    await telegram.answer_callback_query(callback["id"])
    if callback.get("data") == "help":
        chat_id: int | None = (callback.get("from") or {}).get("id")
        if chat_id:
            await telegram.send_help_message(chat_id)


async def handle_start(ctx: HandlerCtx) -> None:
    user = await ctx.user_repo.get_by_telegram_id(ctx.telegram_id)
    if user and user.notion_access_token:
        first_name: str | None = ctx.message.get("from", {}).get("first_name")
        await ctx.telegram.send_welcome_connected(ctx.telegram_id, first_name)
    else:
        token = create_state_token(ctx.telegram_id)
        login_url = (
            settings.NOTION_REDIRECT_URI.replace("/callback", "/login")
            + f"?token={token}"
        )
        await ctx.telegram.send_notion_connect_button(ctx.telegram_id, login_url)


async def handle_memo(ctx: HandlerCtx) -> None:
    memo_text = ctx.text[5:].strip()
    if memo_text:
        logger.info("Processing memo from %s", ctx.telegram_id)
        ctx.background_tasks.add_task(ctx.link_service.process_memo, ctx.telegram_id, memo_text)
    else:
        await ctx.telegram.send_message(
            ctx.telegram_id,
            "메모 내용을 입력해주세요.\n예시: <code>/memo 오늘 배운 내용</code>",
        )


async def handle_search(ctx: HandlerCtx) -> None:
    query = ctx.text[7:].strip()
    if not query:
        await ctx.telegram.send_message(
            ctx.telegram_id,
            "검색어를 입력해주세요.\n예시: <code>/search 인공지능</code>",
        )
        return
    logger.info("Searching for %s from %s", query, ctx.telegram_id)
    results = await ctx.link_service.search(ctx.telegram_id, query)
    await ctx.telegram.send_search_results(ctx.telegram_id, query, results)


async def handle_url(ctx: HandlerCtx, urls: list[str], memo: str | None) -> None:
    for url in urls:
        logger.info("Processing URL from %s: %s", ctx.telegram_id, url)
        ctx.background_tasks.add_task(ctx.link_service.process_link, ctx.telegram_id, url, memo)


async def handle_text(ctx: HandlerCtx) -> None:
    query = ctx.text.strip()
    if not query:
        return
    logger.info("Searching for %s from %s", query, ctx.telegram_id)
    results = await ctx.link_service.search(ctx.telegram_id, query)
    await ctx.telegram.send_search_results(ctx.telegram_id, query, results)


# ── Command Router ───────────────────────────────────────────────────────────

COMMANDS: dict[str, Callable[[HandlerCtx], Awaitable[None]]] = {
    "/start": handle_start,
    "/memo": handle_memo,
    "/search": handle_search,
}
