from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_di import (
    get_notion_client,
    get_telegram_client,
    get_user_repository,
)
from app.infrastructure.database import get_db
from app.infrastructure.external.notion_client import NotionClient
from app.infrastructure.external.scraper_client import ScraperClient
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.llm.openai_client import OpenAIClient
from app.infrastructure.repository.chunk_repository import ChunkRepository
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.repository.user_repository import UserRepository
from app.services.link_service import LinkService
from app.services.memo_service import MemoService
from app.services.notion_service import NotionService
from app.services.search_service import SearchService


def get_openai_client() -> OpenAIClient:
    return OpenAIClient()


def get_scraper_client() -> ScraperClient:
    return ScraperClient()


def get_link_repository(db: AsyncSession = Depends(get_db)) -> LinkRepository:
    return LinkRepository(db)


def get_chunk_repository(db: AsyncSession = Depends(get_db)) -> ChunkRepository:
    return ChunkRepository(db)


def get_notion_service(
    user_repo: UserRepository = Depends(get_user_repository),
    notion: NotionClient = Depends(get_notion_client),
) -> NotionService:
    return NotionService(user_repo, notion)


def get_search_service(
    openai: OpenAIClient = Depends(get_openai_client),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
) -> SearchService:
    return SearchService(openai, chunk_repo)


def get_memo_service(
    db: AsyncSession = Depends(get_db),
    openai: OpenAIClient = Depends(get_openai_client),
    notion_svc: NotionService = Depends(get_notion_service),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    link_repo: LinkRepository = Depends(get_link_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
) -> MemoService:
    return MemoService(db, openai, notion_svc, telegram, user_repo, link_repo, chunk_repo)


def get_link_service(
    db: AsyncSession = Depends(get_db),
    openai: OpenAIClient = Depends(get_openai_client),
    scraper: ScraperClient = Depends(get_scraper_client),
    notion_svc: NotionService = Depends(get_notion_service),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    link_repo: LinkRepository = Depends(get_link_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
) -> LinkService:
    return LinkService(db, openai, scraper, notion_svc, telegram, user_repo, link_repo, chunk_repo)
