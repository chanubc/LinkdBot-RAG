from datetime import datetime, timedelta, timezone

import jwt as pyjwt

from app.core.config import settings

JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 7


def create_dashboard_token(telegram_id: int) -> str:
    payload = {
        "sub": str(telegram_id),
        "exp": datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS),
        "iat": datetime.now(timezone.utc),
    }
    return pyjwt.encode(payload, settings.DASHBOARD_JWT_SECRET, algorithm=JWT_ALGORITHM)


def verify_dashboard_token(token: str) -> int | None:
    try:
        payload = pyjwt.decode(
            token, settings.DASHBOARD_JWT_SECRET, algorithms=[JWT_ALGORITHM]
        )
        return int(payload["sub"])
    except (pyjwt.PyJWTError, KeyError, ValueError):
        return None
