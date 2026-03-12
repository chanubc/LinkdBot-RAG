from fastapi import Depends

from app.api.dependencies.agent_di import get_intent_classifier, get_knowledge_agent
from app.api.dependencies.auth_di import (
    get_auth_service,
    get_telegram_client,
    get_user_repository,
)
from app.api.dependencies.link_di import (
    get_mark_read_usecase,
    get_recall_memo_usecase,
    get_save_link_usecase,
    get_save_memo_usecase,
)
from app.api.dependencies.rag_di import get_search_usecase
from app.api.dependencies.report_di import get_weekly_report_usecase
from app.application.ports.knowledge_agent_port import KnowledgeAgentPort
from app.application.ports.intent_router_port import IntentRouterPort
from app.application.ports.telegram_port import TelegramPort
from app.application.services.auth_service import AuthService
from app.application.services.message_router_service import MessageRouterService
from app.application.services.telegram_webhook_handler import TelegramWebhookHandler
from app.application.usecases.generate_weekly_report_usecase import GenerateWeeklyReportUseCase
from app.application.usecases.mark_read_usecase import MarkReadUseCase
from app.application.usecases.recall_memo_usecase import RecallMemoUseCase
from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.application.usecases.save_memo_usecase import SaveMemoUseCase
from app.application.usecases.search_usecase import SearchUseCase
from app.domain.repositories.i_user_repository import IUserRepository


def get_message_router(
    intent_classifier: IntentRouterPort = Depends(get_intent_classifier),
    agent: KnowledgeAgentPort = Depends(get_knowledge_agent),
    search_uc: SearchUseCase = Depends(get_search_usecase),
    save_memo_uc: SaveMemoUseCase = Depends(get_save_memo_usecase),
    recall_memo_uc: RecallMemoUseCase = Depends(get_recall_memo_usecase),
    weekly_report_uc: GenerateWeeklyReportUseCase = Depends(get_weekly_report_usecase),
    telegram: TelegramPort = Depends(get_telegram_client),
    user_repo: IUserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> MessageRouterService:
    return MessageRouterService(
        intent_classifier,
        agent,
        search_uc,
        save_memo_uc,
        recall_memo_uc,
        weekly_report_uc,
        telegram,
        user_repo,
        auth_service,
    )


def get_webhook_handler(
    message_router: MessageRouterService = Depends(get_message_router),
    telegram: TelegramPort = Depends(get_telegram_client),
    save_link_uc: SaveLinkUseCase = Depends(get_save_link_usecase),
    mark_read_uc: MarkReadUseCase = Depends(get_mark_read_usecase),
    user_repo: IUserRepository = Depends(get_user_repository),
) -> TelegramWebhookHandler:
    return TelegramWebhookHandler(message_router, telegram, save_link_uc, mark_read_uc, user_repo)
