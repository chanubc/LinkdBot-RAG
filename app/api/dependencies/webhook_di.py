from fastapi import Depends

from app.api.dependencies.agent_di import get_knowledge_agent
from app.api.dependencies.auth_di import (
    get_auth_service,
    get_telegram_client,
    get_user_repository,
)
from app.api.dependencies.link_di import get_save_link_usecase, get_save_memo_usecase
from app.api.dependencies.rag_di import get_search_usecase
from app.application.agents.knowledge_agent import KnowledgeAgent
from app.application.services.auth_service import AuthService
from app.application.services.webhook_service import WebhookService
from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.application.usecases.save_memo_usecase import SaveMemoUseCase
from app.application.usecases.search_usecase import SearchUseCase
from app.domain.repositories.i_telegram_repository import ITelegramRepository
from app.infrastructure.repository.user_repository import UserRepository


def get_webhook_service(
    save_link_uc: SaveLinkUseCase = Depends(get_save_link_usecase),
    save_memo_uc: SaveMemoUseCase = Depends(get_save_memo_usecase),
    search_uc: SearchUseCase = Depends(get_search_usecase),
    agent_svc: KnowledgeAgent = Depends(get_knowledge_agent),
    telegram: ITelegramRepository = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> WebhookService:
    return WebhookService(
        save_link_uc, save_memo_uc, search_uc, agent_svc, telegram, user_repo, auth_service
    )
