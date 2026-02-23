from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import get_db
from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.services.auth_service import AuthService


def get_notion_client() -> NotionClient:
    return NotionClient()


def get_telegram_client() -> TelegramClient:
    return TelegramClient()


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


def get_auth_service(
    notion: NotionClient = Depends(get_notion_client),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
) -> AuthService:
    return AuthService(notion, telegram, user_repo)
