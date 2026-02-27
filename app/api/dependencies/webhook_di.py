from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.adapter_di import get_agent, get_intent_classifier
from app.api.dependencies.auth_di import (
    get_auth_service,
    get_telegram_client,
    get_user_repository,
)
from app.api.dependencies.link_di import get_link_repository, get_save_link_usecase, get_save_memo_usecase
from app.api.dependencies.rag_di import get_search_usecase
from app.application.ports.knowledge_agent_port import KnowledgeAgentPort
from app.application.ports.intent_router_port import IntentRouterPort
from app.application.services.auth_service import AuthService
from app.application.services.telegram_webhook_handler import TelegramWebhookHandler
from app.application.services.message_router_service import MessageRouterService
from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.application.usecases.save_memo_usecase import SaveMemoUseCase
from app.application.usecases.search_usecase import SearchUseCase
from app.application.ports.telegram_port import TelegramPort
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.database import get_db
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.repository.user_repository import UserRepository


def get_message_router(
    intent_classifier: IntentRouterPort = Depends(get_intent_classifier),
    agent: KnowledgeAgentPort = Depends(get_agent),
    search_uc: SearchUseCase = Depends(get_search_usecase),
    save_memo_uc: SaveMemoUseCase = Depends(get_save_memo_usecase),
    telegram: TelegramPort = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageRouterService:
    return MessageRouterService(
        intent_classifier, agent, search_uc, save_memo_uc, telegram, user_repo, auth_service
    )


def get_webhook_handler(
    db: AsyncSession = Depends(get_db),
    message_router: MessageRouterService = Depends(get_message_router),
    telegram: TelegramPort = Depends(get_telegram_client),
    save_link_uc: SaveLinkUseCase = Depends(get_save_link_usecase),
    user_repo: IUserRepository = Depends(get_user_repository),
    link_repo: ILinkRepository = Depends(get_link_repository),
) -> TelegramWebhookHandler:
    return TelegramWebhookHandler(db, message_router, telegram, save_link_uc, user_repo, link_repo)
