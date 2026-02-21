from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository

router = APIRouter()


@router.get("/notion/login")
async def notion_login(telegram_id: int = Query(...)):
    """Notion OAuth 인증 시작 — Notion 로그인 페이지로 리다이렉트."""
    url = (
        "https://api.notion.com/v1/oauth/authorize"
        f"?client_id={settings.NOTION_CLIENT_ID}"
        "&response_type=code"
        "&owner=user"
        f"&redirect_uri={settings.NOTION_REDIRECT_URI}"
        f"&state={telegram_id}"
    )
    return RedirectResponse(url=url)


@router.get("/notion/callback")
async def notion_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Notion OAuth 콜백 — 토큰 발급 후 DB에 저장."""
    telegram_id = int(state)
    notion = NotionClient()

    token_data = await notion.exchange_code(code)
    access_token: str = token_data["access_token"]

    # 봇이 접근 가능한 첫 번째 페이지를 부모로 사용
    page_id = await notion.get_accessible_page_id(access_token)

    user_repo = UserRepository(db)
    await user_repo.upsert_notion_credentials(
        telegram_id=telegram_id,
        notion_access_token=access_token,
        notion_page_id=page_id,
    )

    # 텔레그램으로 연동 완료 알림
    await TelegramClient().send_message(
        telegram_id,
        "✅ Notion 연동이 완료됐습니다!\n이제 링크를 전송하면 자동으로 저장됩니다.",
    )

    return HTMLResponse(
        content="<h2>✅ Notion 연동 완료!</h2><p>텔레그램으로 돌아가서 링크를 전송해보세요.</p>",
        status_code=200,
    )
