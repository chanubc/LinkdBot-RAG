from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_di import (
    get_notion_client,
    get_telegram_client,
    get_user_repository,
)
from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.application.usecases.save_memo_usecase import SaveMemoUseCase
from app.application.ports.notion_port import NotionPort
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.ports.scraper_port import ScraperPort
from app.application.ports.telegram_port import TelegramPort
from app.core.config import settings
from app.infrastructure.database import get_db
from app.infrastructure.external.jina_reader_adapter import JinaReaderAdapter
from app.infrastructure.external.scraper_client import ScraperRepository
from app.infrastructure.llm.openai_client import OpenAIRepository
from app.infrastructure.repository.chunk_repository import ChunkRepository
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.repository.user_repository import UserRepository


def get_openai_client() -> AIAnalysisPort:
    return OpenAIRepository()


def get_scraper_client() -> ScraperPort:
    """JINA_API_KEY 설정 시 JinaReaderAdapter, 미설정 시 OG ScraperRepository 사용."""
    if settings.JINA_API_KEY:
        return JinaReaderAdapter(api_key=settings.JINA_API_KEY)
    return ScraperRepository()


def get_link_repository(db: AsyncSession = Depends(get_db)) -> LinkRepository:
    return LinkRepository(db)


def get_chunk_repository(db: AsyncSession = Depends(get_db)) -> ChunkRepository:
    return ChunkRepository(db)


def get_save_link_usecase(
    db: AsyncSession = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
    link_repo: LinkRepository = Depends(get_link_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    openai: AIAnalysisPort = Depends(get_openai_client),
    scraper: ScraperPort = Depends(get_scraper_client),
    telegram: TelegramPort = Depends(get_telegram_client),
    notion: NotionPort = Depends(get_notion_client),
) -> SaveLinkUseCase:
    return SaveLinkUseCase(db, user_repo, link_repo, chunk_repo, openai, scraper, telegram, notion)


def get_save_memo_usecase(
    db: AsyncSession = Depends(get_db),
    user_repo: UserRepository = Depends(get_user_repository),
    link_repo: LinkRepository = Depends(get_link_repository),
    chunk_repo: ChunkRepository = Depends(get_chunk_repository),
    openai: AIAnalysisPort = Depends(get_openai_client),
    telegram: TelegramPort = Depends(get_telegram_client),
    notion: NotionPort = Depends(get_notion_client),
) -> SaveMemoUseCase:
    return SaveMemoUseCase(db, user_repo, link_repo, chunk_repo, openai, telegram, notion)
