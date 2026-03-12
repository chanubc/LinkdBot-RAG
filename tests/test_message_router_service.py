"""Test MessageRouterService Telegram-first UX changes."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.ports.intent_router_port import RouterOutput as ClassifierOutput
from app.application.ports.knowledge_agent_port import KnowledgeAnswer, KnowledgeSource
from app.application.services.message_router_service import MessageRouterService
from app.domain.entities.intent import Intent


@pytest.fixture
def mock_dependencies():
    agent = AsyncMock()
    agent.answer.return_value = KnowledgeAnswer(answer="답변", sources=[])
    return {
        "intent_classifier": AsyncMock(),
        "agent": agent,
        "search_uc": AsyncMock(),
        "save_memo_uc": AsyncMock(),
        "recall_memo_uc": AsyncMock(),
        "weekly_report_uc": AsyncMock(),
        "telegram": AsyncMock(),
        "user_repo": AsyncMock(),
        "auth_service": MagicMock(),
    }


@pytest.fixture
def router_service(mock_dependencies):
    return MessageRouterService(**mock_dependencies)


@pytest.mark.asyncio
async def test_route_empty_text(router_service):
    await router_service.route(123, "")
    assert router_service._intent_classifier.classify.called is False


@pytest.mark.asyncio
async def test_slash_command_with_handler_map(router_service, mock_dependencies):
    await router_service.route(123, "/start")
    assert mock_dependencies["user_repo"].get_by_telegram_id.called

    mock_dependencies["telegram"].reset_mock()
    await router_service.route(123, "/help")
    assert mock_dependencies["telegram"].send_help_message.called


@pytest.mark.asyncio
async def test_menu_command_sends_menu_message(router_service, mock_dependencies):
    mock_dependencies["user_repo"].get_by_telegram_id.return_value = type(
        "User", (), {"notion_database_id": "abcd-1234", "notion_access_token": "token", "first_name": "A"}
    )()

    with patch("app.core.jwt.create_dashboard_token", return_value="menu.jwt"):
        await router_service.route(123, "/menu")

    mock_dependencies["telegram"].send_menu_message.assert_awaited_once()
    args = mock_dependencies["telegram"].send_menu_message.call_args[0]
    assert args[0] == 123
    assert "menu.jwt" in args[1]
    assert args[2] == "https://www.notion.so/abcd1234"


@pytest.mark.asyncio
async def test_report_command_runs_usecase(router_service, mock_dependencies):
    await router_service.route(123, "/report")

    assert mock_dependencies["weekly_report_uc"].execute.await_count == 1
    assert mock_dependencies["weekly_report_uc"].execute.await_args.args == (123,)
    progress_messages = [call.args[1] for call in mock_dependencies["telegram"].send_message.await_args_list]
    assert any("주간 리포트" in message for message in progress_messages)
    assert any("관심사" in message for message in progress_messages)


@pytest.mark.asyncio
async def test_memo_command_without_payload(router_service, mock_dependencies):
    await router_service.route(123, "/memo")
    args = mock_dependencies["telegram"].send_message.call_args[0]
    assert "메모 내용을 입력해주세요" in args[1]
    assert mock_dependencies["save_memo_uc"].execute.called is False


@pytest.mark.asyncio
async def test_intent_dispatch_with_handler_map(router_service, mock_dependencies):
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.SEARCH,
        query="test query",
    )

    await router_service.route(123, "search something")
    assert mock_dependencies["search_uc"].execute.called


@pytest.mark.asyncio
async def test_intent_memo_recall_dispatch(router_service, mock_dependencies):
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.MEMO_RECALL,
        query=None,
        time_filter="yesterday",
    )

    await router_service.route(123, "어제 작성한 메모 가져와")

    mock_dependencies["recall_memo_uc"].execute.assert_called_once_with(
        telegram_id=123,
        query="",
        time_filter="yesterday",
    )


@pytest.mark.asyncio
async def test_likely_question_bypasses_classifier(router_service, mock_dependencies):
    await router_service.route(123, "RAG가 뭐야?")

    mock_dependencies["intent_classifier"].classify.assert_not_called()
    mock_dependencies["agent"].answer.assert_called_once_with(123, "RAG가 뭐야?")


@pytest.mark.asyncio
async def test_help_like_question_still_uses_classifier(router_service, mock_dependencies):
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.HELP,
        query=None,
    )

    await router_service.route(123, "how do I use this bot?")

    mock_dependencies["intent_classifier"].classify.assert_called_once()
    mock_dependencies["agent"].answer.assert_not_called()


@pytest.mark.asyncio
async def test_unknown_slash_command_feedback(router_service, mock_dependencies):
    await router_service.route(123, "/unknown command arg")
    args = mock_dependencies["telegram"].send_message.call_args[0]
    assert "알 수 없는 명령어" in args[1]
    assert "/help" in args[1]


@pytest.mark.asyncio
async def test_dashboard_command_sends_url(router_service, mock_dependencies):
    with patch("app.core.jwt.create_dashboard_token", return_value="test.jwt.token") as mock_create_token:
        await router_service.route(123, "/dashboard")

        mock_create_token.assert_called_once_with(123)
        mock_dependencies["telegram"].send_dashboard_button.assert_called_once()
        call_args = mock_dependencies["telegram"].send_dashboard_button.call_args[0]
        assert call_args[0] == 123
        assert "test.jwt.token" in call_args[1]


@pytest.mark.asyncio
async def test_handler_map_extensibility(router_service):
    assert "/menu" in router_service._slash_handlers
    assert "/report" in router_service._slash_handlers
    assert "/dashboard" in router_service._slash_handlers
    assert router_service._slash_handlers["/menu"] == router_service._handle_menu
    assert router_service._slash_handlers["/report"] == router_service._handle_report


@pytest.mark.asyncio
async def test_ask_flow_sends_two_progress_messages_and_structured_response(router_service, mock_dependencies):
    mock_dependencies["agent"].answer.return_value = KnowledgeAnswer(
        answer="최종 답변",
        sources=[KnowledgeSource(title="RAG 문서", url="https://example.com/rag", link_id=7)],
    )

    await router_service.route(123, "RAG가 뭐야?")

    send_message_calls = mock_dependencies["telegram"].send_message.await_args_list
    assert send_message_calls[0].args == (123, "🤖 질문을 확인했어요. 답변 준비를 시작합니다...")
    assert send_message_calls[1].args == (123, "📚 저장된 지식과 메모를 찾는 중입니다...")
    mock_dependencies["telegram"].send_ask_response.assert_awaited_once_with(
        123,
        answer_text="최종 답변",
        sources=[KnowledgeSource(title="RAG 문서", url="https://example.com/rag", link_id=7)],
    )


@pytest.mark.asyncio
async def test_search_flow_sends_two_progress_messages_and_results(router_service, mock_dependencies):
    mock_dependencies["search_uc"].execute.return_value = [{"title": "Doc", "link_id": 9, "similarity": 0.9}]

    await router_service.route(123, "/search rag")

    send_message_calls = mock_dependencies["telegram"].send_message.await_args_list
    assert send_message_calls[0].args == (123, "🔍 검색 요청을 받았어요. 관련 링크를 찾는 중입니다...")
    assert send_message_calls[1].args == (123, "📚 저장된 링크를 스캔하고 있어요...")
    mock_dependencies["telegram"].send_search_results.assert_awaited_once_with(
        123,
        "rag",
        [{"title": "Doc", "link_id": 9, "similarity": 0.9}],
    )


@pytest.mark.asyncio
async def test_run_safe_error_handling(router_service, mock_dependencies):
    mock_coro = AsyncMock(side_effect=Exception("Test error"))

    await router_service._run_safe(123, mock_coro, "arg1", error_msg="Custom error")

    args = mock_dependencies["telegram"].send_message.call_args[0]
    assert "Custom error" in args[1]
