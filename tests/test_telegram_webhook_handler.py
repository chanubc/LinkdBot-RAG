from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import BackgroundTasks

from app.application.services.telegram_webhook_handler import TelegramWebhookHandler


@pytest.fixture
def webhook_dependencies():
    return {
        "message_router": AsyncMock(),
        "telegram": AsyncMock(),
        "save_link_uc": AsyncMock(),
        "mark_read_uc": AsyncMock(),
        "user_repo": AsyncMock(),
    }


@pytest.fixture
def webhook_handler(webhook_dependencies):
    return TelegramWebhookHandler(**webhook_dependencies)


@pytest.mark.asyncio
async def test_handle_url_message_schedules_save_link_usecase(webhook_handler, webhook_dependencies):
    background_tasks = MagicMock(spec=BackgroundTasks)
    data = {
        "message": {
            "text": "https://example.com 메모",
            "from": {"id": 123, "first_name": "Chanu"},
            "chat": {"id": 123},
        }
    }

    await webhook_handler.handle(data, background_tasks)

    webhook_dependencies["user_repo"].ensure_exists.assert_awaited_once_with(123, "Chanu")
    background_tasks.add_task.assert_called_once_with(
        webhook_dependencies["save_link_uc"].execute,
        123,
        "https://example.com",
        "메모",
    )


@pytest.mark.asyncio
async def test_handle_plain_message_schedules_router_without_nested_background_arg(
    webhook_handler, webhook_dependencies
):
    background_tasks = MagicMock(spec=BackgroundTasks)
    data = {
        "message": {
            "text": "RAG가 뭐야?",
            "from": {"id": 123, "first_name": "Chanu"},
            "chat": {"id": 123},
        }
    }

    await webhook_handler.handle(data, background_tasks)

    background_tasks.add_task.assert_called_once_with(
        webhook_dependencies["message_router"].route,
        123,
        "RAG가 뭐야?",
    )


@pytest.mark.asyncio
async def test_help_callback_routes_to_telegram_help(webhook_handler, webhook_dependencies):
    callback = {
        "id": "callback-1",
        "data": "help",
        "from": {"id": 123},
    }

    await webhook_handler._handle_callback(callback)

    webhook_dependencies["telegram"].answer_callback_query.assert_awaited_once_with("callback-1")
    webhook_dependencies["telegram"].send_help_message.assert_awaited_once_with(123)


@pytest.mark.asyncio
async def test_mark_read_callback_uses_usecase_and_sends_success_message(
    webhook_handler, webhook_dependencies
):
    webhook_dependencies["mark_read_uc"].execute.return_value = True
    callback = {
        "id": "callback-2",
        "data": "mark_read:7",
        "from": {"id": 123},
    }

    await webhook_handler._handle_callback(callback)

    webhook_dependencies["mark_read_uc"].execute.assert_awaited_once_with(123, 7)
    webhook_dependencies["telegram"].send_message.assert_awaited_once_with(123, "✅ 읽음 처리되었습니다.")
