from app.api.dependencies.agent_di import get_knowledge_agent
from app.api.dependencies.auth_di import (
    get_auth_service,
    get_notion_client,
    get_telegram_client,
    get_user_repository,
)
from app.api.dependencies.link_di import (
    get_chunk_repository,
    get_link_repository,
    get_mark_read_usecase,
    get_openai_client,
    get_save_link_usecase,
    get_save_memo_usecase,
    get_scraper_client,
)
from app.api.dependencies.rag_di import get_search_usecase
from app.api.dependencies.webhook_di import get_webhook_handler

__all__ = [
    "get_notion_client",
    "get_telegram_client",
    "get_user_repository",
    "get_auth_service",
    "get_openai_client",
    "get_scraper_client",
    "get_link_repository",
    "get_chunk_repository",
    "get_mark_read_usecase",
    "get_save_link_usecase",
    "get_save_memo_usecase",
    "get_search_usecase",
    "get_knowledge_agent",
    "get_webhook_handler",
]
