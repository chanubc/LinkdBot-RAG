import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse

logger = logging.getLogger(__name__)

from app.api.dependencies import get_auth_service
from app.config import settings
from app.infrastructure.state_store import consume as consume_state_token
from app.services.auth_service import AuthService

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
    auth_service: AuthService = Depends(get_auth_service),
):
    """Notion OAuth 콜백 — 토큰 발급 후 DB에 저장."""
    telegram_id = int(state.split("_", 1)[1])
    await auth_service.complete_notion_oauth(code, telegram_id)
    return HTMLResponse(
        content="<h2>✅ Notion 연동 완료!</h2><p>텔레그램으로 돌아가서 링크를 전송해보세요.</p>",
        status_code=200,
    )
