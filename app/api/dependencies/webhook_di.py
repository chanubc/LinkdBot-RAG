from fastapi import Depends

from app.api.dependencies.auth_di import (
    get_auth_service,
    get_telegram_client,
    get_user_repository,
)
from app.api.dependencies.link_di import (
    get_link_service,
    get_memo_service,
    get_search_service,
)
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.link_service import LinkService
from app.services.memo_service import MemoService
from app.services.search_service import SearchService
from app.services.webhook_service import WebhookService


def get_webhook_service(
    link_service: LinkService = Depends(get_link_service),
    memo_service: MemoService = Depends(get_memo_service),
    search_service: SearchService = Depends(get_search_service),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> WebhookService:
    return WebhookService(link_service, memo_service, search_service, telegram, user_repo, auth_service)
