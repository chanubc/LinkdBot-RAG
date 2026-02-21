import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

from app.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.infrastructure.state_store import consume as consume_state_token

router = APIRouter()


@router.get("/notion/login")
async def notion_login(token: str = Query(...)):
    """Notion OAuth 인증 시작 — Notion 로그인 페이지로 리다이렉트."""
    telegram_id = consume_state_token(token)
    if telegram_id is None:
        raise HTTPException(status_code=400, detail="유효하지 않거나 만료된 링크입니다.")
    url = (
        "https://api.notion.com/v1/oauth/authorize"
        f"?client_id={settings.NOTION_CLIENT_ID}"
        "&response_type=code"
        "&owner=user"
        f"&redirect_uri={settings.NOTION_REDIRECT_URI}"
        f"&state=tg_{telegram_id}"
    )
    return RedirectResponse(url=url)


@router.get("/notion/callback")
async def notion_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Notion OAuth 콜백 — 토큰 발급 후 DB에 저장."""
    telegram_id = int(state.split("_", 1)[1])
    notion = NotionClient()

    token_data = await notion.exchange_code(code)
    access_token: str = token_data["access_token"]

    # 접근 가능한 첫 번째 페이지 하위에 LinkdBot DB 자동 생성
    page_id = await notion.get_accessible_page_id(access_token)
    database_id: str | None = None
    if page_id:
        try:
            database_id = await notion.create_database(access_token, page_id)
        except Exception:
            logger.exception("Notion DB 생성 실패 (telegram_id=%s)", telegram_id)

    user_repo = UserRepository(db)
    await user_repo.upsert_notion_credentials(
        telegram_id=telegram_id,
        notion_access_token=access_token,
        notion_database_id=database_id,
    )

    telegram = TelegramClient()
    if database_id:
        await telegram.send_message(
            telegram_id,
            "✅ Notion 연동이 완료됐습니다!\n이제 링크를 전송하면 자동으로 저장됩니다.",
        )
    else:
        await telegram.send_message(
            telegram_id,
            "⚠️ Notion 계정 연동은 됐지만 데이터베이스를 생성하지 못했습니다.\n"
            "봇이 접근 가능한 Notion 페이지가 없습니다. "
            "Notion에서 페이지 접근 권한을 허용한 뒤 /start로 다시 시도해주세요.",
        )

    return HTMLResponse(
        content="<h2>✅ Notion 연동 완료!</h2><p>텔레그램으로 돌아가서 링크를 전송해보세요.</p>",
        status_code=200,
    )
