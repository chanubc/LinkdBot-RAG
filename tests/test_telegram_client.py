from unittest.mock import AsyncMock

import pytest

from app.application.ports.knowledge_agent_port import KnowledgeSource
from app.infrastructure.external.telegram_client import TelegramRepository


@pytest.fixture
def telegram_repo():
    repo = TelegramRepository()
    repo._post_message = AsyncMock()  # type: ignore[attr-defined]
    return repo


@pytest.mark.asyncio
async def test_send_help_message_mentions_report_and_dashboard_separately(telegram_repo):
    await telegram_repo.send_help_message(123)

    telegram_repo._post_message.assert_awaited_once()  # type: ignore[attr-defined]
    payload = telegram_repo._post_message.await_args.args[0]  # type: ignore[attr-defined]

    assert payload["chat_id"] == 123
    assert "<code>/report</code>" in payload["text"]
    assert "텔레그램에서 바로 주간 리포트를 생성해요." in payload["text"]
    assert "<code>/dashboard</code>" in payload["text"]


@pytest.mark.asyncio
async def test_send_search_results_adds_mark_read_buttons(telegram_repo):
    await telegram_repo.send_search_results(
        123,
        "rag",
        [
            {"title": "RAG 문서", "url": "https://example.com/rag", "similarity": 0.92, "link_id": 7},
            {"title": "No Button", "url": "https://example.com/no-btn", "similarity": 0.8},
        ],
    )

    payload = telegram_repo._post_message.await_args.args[0]  # type: ignore[attr-defined]

    assert "reply_markup" in payload
    assert payload["reply_markup"]["inline_keyboard"] == [
        [{"text": "✅ 1번 읽음 처리", "callback_data": "mark_read:7"}],
        [{"text": "« Back to Menu", "callback_data": "nav:menu"}],
    ]


@pytest.mark.asyncio
async def test_send_ask_response_adds_source_mark_read_buttons(telegram_repo):
    await telegram_repo.send_ask_response(
        123,
        "최종 답변",
        [
            KnowledgeSource(title="RAG 문서", url="https://example.com/rag", link_id=11),
            KnowledgeSource(title="버튼 없음", url=None, link_id=None),
        ],
    )

    payload = telegram_repo._post_message.await_args.args[0]  # type: ignore[attr-defined]

    assert payload["text"].startswith("최종 답변")
    assert payload["reply_markup"]["inline_keyboard"] == [
        [{"text": "✅ 출처 1 읽음 처리", "callback_data": "mark_read:11"}],
        [{"text": "« Back to Menu", "callback_data": "nav:menu"}],
    ]


@pytest.mark.asyncio
async def test_send_menu_message_has_back_row_at_bottom(telegram_repo):
    await telegram_repo.send_menu_message(
        chat_id=123,
        dashboard_url="https://dash.example.com",
        notion_url="https://www.notion.so/abcd",
    )

    payload = telegram_repo._post_message.await_args.args[0]  # type: ignore[attr-defined]
    assert payload["reply_markup"]["inline_keyboard"][-1] == [
        {"text": "« Back to Menu", "callback_data": "nav:menu"}
    ]


@pytest.mark.asyncio
async def test_send_weekly_report_adds_back_button_row(telegram_repo):
    await telegram_repo.send_weekly_report(123, "weekly text", link_id=9)

    payload = telegram_repo._post_message.await_args.args[0]  # type: ignore[attr-defined]
    assert payload["reply_markup"]["inline_keyboard"] == [
        [{"text": "✅ 읽음 처리", "callback_data": "mark_read:9"}],
        [{"text": "« Back to Menu", "callback_data": "nav:menu"}],
    ]
