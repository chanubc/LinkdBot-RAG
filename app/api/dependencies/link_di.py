from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_di import (
    get_notion_client,
    get_telegram_client,
    get_user_repository,
)
from app.infrastructure.database import get_db
from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.repository.user_repository import UserRepository
from app.services.link_service import LinkService


def get_openai_client() -> OpenAIClient:
    return OpenAIClient()


def get_link_repository(db: AsyncSession = Depends(get_db)) -> LinkRepository:
    return LinkRepository(db)


def get_link_service(
    openai: OpenAIClient = Depends(get_openai_client),
    notion: NotionClient = Depends(get_notion_client),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    link_repo: LinkRepository = Depends(get_link_repository),
) -> LinkService:
    return LinkService(openai, notion, telegram, user_repo, link_repo)
