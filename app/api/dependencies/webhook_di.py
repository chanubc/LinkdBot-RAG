from fastapi import Depends

from app.api.dependencies.auth_di import (
    get_auth_service,
    get_telegram_client,
    get_user_repository,
)
from app.api.dependencies.link_di import get_link_service
from app.infrastructure.external.telegram_client import TelegramClient
from app.infrastructure.repository.user_repository import UserRepository
from app.services.auth_service import AuthService
from app.services.link_service import LinkService
from app.services.webhook_service import WebhookService


def get_webhook_service(
    link_service: LinkService = Depends(get_link_service),
    telegram: TelegramClient = Depends(get_telegram_client),
    user_repo: UserRepository = Depends(get_user_repository),
    auth_service: AuthService = Depends(get_auth_service),
) -> WebhookService:
    return WebhookService(link_service, telegram, user_repo, auth_service)
