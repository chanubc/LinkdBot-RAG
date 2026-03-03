from fastapi import Depends, Header, HTTPException

from app.core.jwt import verify_dashboard_token


async def get_dashboard_telegram_id(
    authorization: str | None = Header(None, alias="Authorization"),
) -> int:
    if not authorization:
        raise HTTPException(status_code=401, detail="Bearer token required")
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Bearer token required")
    token = authorization.removeprefix("Bearer ")
    telegram_id = verify_dashboard_token(token)
    if telegram_id is None:
        raise HTTPException(
            status_code=401, detail="Invalid or expired dashboard token"
        )
    return telegram_id
