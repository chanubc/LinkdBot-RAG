from functools import lru_cache

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.auth_service import AuthService
from app.application.ports.notion_port import NotionPort
from app.application.ports.telegram_port import TelegramPort
from app.infrastructure.database import get_db
from app.infrastructure.external.notion_client import NotionRepository
from app.infrastructure.external.telegram_client import TelegramRepository
from app.infrastructure.repository.user_repository import UserRepository
from app.infrastructure.state_store import InMemoryStateStore


def get_notion_client() -> NotionPort:
    return NotionRepository()


def get_telegram_client() -> TelegramPort:
    return TelegramRepository()


def get_user_repository(db: AsyncSession = Depends(get_db)) -> UserRepository:
    return UserRepository(db)


@lru_cache(maxsize=None)
def get_state_store() -> InMemoryStateStore:
    """요청 간 상태 공유를 위한 프로세스 싱글턴."""
    return InMemoryStateStore()


def get_auth_service(
    db: AsyncSession = Depends(get_db),
    notion: NotionPort = Depends(get_notion_client),
    telegram: TelegramPort = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    state_store: InMemoryStateStore = Depends(get_state_store),
) -> AuthService:
    return AuthService(db, notion, telegram, user_repo, state_store)
