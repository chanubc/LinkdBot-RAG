"""Test MessageRouterService refactoring improvements."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from app.application.services.message_router_service import MessageRouterService
from app.domain.entities.intent import Intent
from app.application.ports.intent_router_port import RouterOutput as ClassifierOutput


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for MessageRouterService."""
    agent = AsyncMock()
    agent.answer.return_value = "답변"
    return {
        "intent_classifier": AsyncMock(),
        "agent": agent,
        "search_uc": AsyncMock(),
        "save_memo_uc": AsyncMock(),
        "recall_memo_uc": AsyncMock(),
        "telegram": AsyncMock(),
        "user_repo": AsyncMock(),
        "auth_service": MagicMock(),
    }


@pytest.fixture
def router_service(mock_dependencies):
    """Create MessageRouterService with mocked dependencies."""
    return MessageRouterService(**mock_dependencies)


@pytest.mark.asyncio
async def test_route_empty_text(router_service):
    """Test that empty text is ignored."""
    await router_service.route(123, "")
    # Should return early without any processing
    assert router_service._intent_classifier.classify.called is False


@pytest.mark.asyncio
async def test_slash_command_with_handler_map(router_service, mock_dependencies):
    """Test slash command dispatch using handler map."""
    # Test /start command
    await router_service.route(123, "/start")
    assert mock_dependencies["user_repo"].get_by_telegram_id.called

    # Test /help command
    mock_dependencies["telegram"].reset_mock()
    await router_service.route(123, "/help")
    assert mock_dependencies["telegram"].send_help_message.called


@pytest.mark.asyncio
async def test_memo_command_with_payload(router_service, mock_dependencies):
    """Test /memo command with payload."""
    await router_service.route(123, "/memo 오늘 배운 내용")

    # Should call save_memo_uc.execute
    assert mock_dependencies["save_memo_uc"].execute.called


@pytest.mark.asyncio
async def test_memo_command_without_payload(router_service, mock_dependencies):
    """Test /memo command without payload shows error message."""
    await router_service.route(123, "/memo")

    # Should send error message, not execute save
    mock_dependencies["telegram"].send_message.assert_called_once()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "메모 내용을 입력해주세요" in args[0][1]
    assert mock_dependencies["save_memo_uc"].execute.called is False


@pytest.mark.asyncio
async def test_ask_command_without_payload(router_service, mock_dependencies):
    """Test /ask command without payload."""
    await router_service.route(123, "/ask")

    # Should send error message
    mock_dependencies["telegram"].send_message.assert_called_once()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "질문을 입력해주세요" in args[0][1]


@pytest.mark.asyncio
async def test_intent_dispatch_with_handler_map(router_service, mock_dependencies):
    """Test intent dispatch using handler map."""
    # Mock intent classification
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.SEARCH,
        query="test query"
    )

    await router_service.route(123, "search something")

    # Should dispatch to search handler via handler map
    assert mock_dependencies["search_uc"].execute.called


@pytest.mark.asyncio
async def test_intent_memo_dispatch(router_service, mock_dependencies):
    """Test Intent.MEMO dispatch via handler map."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.MEMO,
        query="test memo"
    )

    await router_service.route(123, "save this memo")

    assert mock_dependencies["save_memo_uc"].execute.called


@pytest.mark.asyncio
async def test_intent_ask_dispatch(router_service, mock_dependencies):
    """Test Intent.ASK dispatch via handler map."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.ASK,
        query="test question"
    )

    await router_service.route(123, "ask me something")

    assert mock_dependencies["agent"].answer.called


@pytest.mark.asyncio
async def test_intent_memo_recall_dispatch(router_service, mock_dependencies):
    """Test Intent.MEMO_RECALL dispatch with time filter."""
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
async def test_memo_recall_sends_formatted_results(router_service, mock_dependencies):
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.MEMO_RECALL,
        query="RAG",
        time_filter="yesterday",
    )
    mock_dependencies["recall_memo_uc"].execute.return_value = [
        {
            "memo": "어제 정리한 RAG 메모",
            "created_at": "2026-03-10T09:00:00+00:00",
        }
    ]

    await router_service.route(123, "어제 RAG 메모 보여줘")

    last_call = mock_dependencies["telegram"].send_message.call_args_list[-1][0]
    assert last_call[0] == 123
    assert "메모 조회 결과" in last_call[1]
    assert "어제 정리한 RAG 메모" in last_call[1]
    assert "2026-03-10" in last_call[1]


@pytest.mark.asyncio
async def test_memo_recall_empty_result_sends_not_found(router_service, mock_dependencies):
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.MEMO_RECALL,
        query=None,
        time_filter="today",
    )
    mock_dependencies["recall_memo_uc"].execute.return_value = []

    await router_service.route(123, "오늘 메모 보여줘")

    last_call = mock_dependencies["telegram"].send_message.call_args_list[-1][0]
    assert "찾지 못했어요" in last_call[1]
    assert "today" in last_call[1]


@pytest.mark.asyncio
async def test_likely_question_bypasses_classifier(router_service, mock_dependencies):
    """질문형 텍스트는 classifier를 우회하고 agent로 바로 전달된다."""
    await router_service.route(123, "RAG가 뭐야?")

    mock_dependencies["intent_classifier"].classify.assert_not_called()
    mock_dependencies["agent"].answer.assert_called_once_with(123, "RAG가 뭐야?")


@pytest.mark.asyncio
async def test_help_like_question_still_uses_classifier(router_service, mock_dependencies):
    """도움말/시작 성격 문장은 질문형이어도 classifier 우선."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.HELP,
        query=None,
    )

    await router_service.route(123, "how do I use this bot?")

    mock_dependencies["intent_classifier"].classify.assert_called_once()
    mock_dependencies["agent"].answer.assert_not_called()


@pytest.mark.asyncio
async def test_start_like_question_still_uses_classifier(router_service, mock_dependencies):
    """시작/연동 성격 문장도 classifier 경유."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.START,
        query=None,
    )

    await router_service.route(123, "Can you guide me to connect notion?")

    mock_dependencies["intent_classifier"].classify.assert_called_once()
    mock_dependencies["agent"].answer.assert_not_called()


@pytest.mark.asyncio
async def test_error_handling_on_classification_failure(router_service, mock_dependencies):
    """Test error handling when intent classification fails."""
    mock_dependencies["intent_classifier"].classify.side_effect = Exception("API Error")

    await router_service.route(123, "some text")

    # Should send help message and not crash
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "/help" in args[0][1]


@pytest.mark.asyncio
async def test_error_handling_on_search_failure(router_service, mock_dependencies):
    """Test error handling when search fails."""
    mock_dependencies["search_uc"].execute.side_effect = Exception("Search Error")

    await router_service.route(123, "/search test")

    # Should send error message
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "오류" in args[0][1]


@pytest.mark.asyncio
async def test_error_handling_on_memo_save_failure(router_service, mock_dependencies):
    """Test error handling when memo save fails."""
    mock_dependencies["save_memo_uc"].execute.side_effect = Exception("DB Error")

    await router_service.route(123, "/memo test")

    # Should send error message
    assert mock_dependencies["telegram"].send_message.called
    # Last call should be error message
    last_call = mock_dependencies["telegram"].send_message.call_args_list[-1]
    assert "오류" in last_call[0][1]


@pytest.mark.asyncio
async def test_unknown_intent_handling(router_service, mock_dependencies):
    """Test handling of unknown intent (Intent.UNKNOWN)."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.UNKNOWN,  # Unknown intent
        query="test"
    )

    await router_service.route(123, "weird text")

    # Should send help message (UNKNOWN not in handler map, so fallback)
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args_list[-1]
    assert "/help" in args[0][1]


@pytest.mark.asyncio
async def test_unknown_slash_command_feedback(router_service, mock_dependencies):
    """Test that unknown slash commands receive feedback (not silent failure)."""
    await router_service.route(123, "/unknown command arg")

    # Should send error message about unknown command
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args[0]
    assert "알 수 없는 명령어" in args[1]
    assert "/help" in args[1]


@pytest.mark.asyncio
async def test_handler_map_extensibility(router_service):
    """Test that handler map can be extended with new handlers."""
    # Verify handler maps exist
    assert hasattr(router_service, "_slash_handlers")
    assert hasattr(router_service, "_intent_handlers")

    # Verify expected handlers are registered
    assert "/start" in router_service._slash_handlers
    assert "/help" in router_service._slash_handlers
    assert "/memo" in router_service._slash_handlers
    assert "/ask" in router_service._slash_handlers
    assert "/search" in router_service._slash_handlers

    # Verify handlers point to core methods (no wrapper indirection)
    assert router_service._slash_handlers["/start"] == router_service._handle_start
    assert router_service._slash_handlers["/help"] == router_service._handle_help
    assert router_service._slash_handlers["/memo"] == router_service._process_memo
    assert router_service._slash_handlers["/ask"] == router_service._process_ask
    assert router_service._slash_handlers["/search"] == router_service._process_search

    assert Intent.SEARCH in router_service._intent_handlers
    assert Intent.MEMO in router_service._intent_handlers
    assert Intent.ASK in router_service._intent_handlers
    assert Intent.MEMO_RECALL in router_service._intent_handlers
    assert Intent.START in router_service._intent_handlers
    assert Intent.HELP in router_service._intent_handlers

    # Verify intent handlers also point directly to core methods
    assert router_service._intent_handlers[Intent.SEARCH] == router_service._process_search
    assert router_service._intent_handlers[Intent.MEMO] == router_service._process_memo
    assert router_service._intent_handlers[Intent.ASK] == router_service._process_ask
    assert router_service._intent_handlers[Intent.MEMO_RECALL] == router_service._process_memo_recall
    assert router_service._intent_handlers[Intent.START] == router_service._handle_start
    assert router_service._intent_handlers[Intent.HELP] == router_service._handle_help


@pytest.mark.asyncio
async def test_run_safe_without_background_tasks(router_service, mock_dependencies):
    """Test _run_safe executes wrapped coroutine directly."""
    mock_coro = AsyncMock()

    await router_service._run_safe(123, mock_coro, "arg1", "arg2")

    mock_coro.assert_called_once_with("arg1", "arg2")


@pytest.mark.asyncio
async def test_dashboard_command_sends_url(router_service, mock_dependencies):
    """/dashboard 명령어 → create_dashboard_token → ?token= URL이 포함된 메시지 전송."""
    with patch("app.core.jwt.create_dashboard_token", return_value="test.jwt.token") as mock_create_token:
        await router_service.route(123, "/dashboard")

        mock_create_token.assert_called_once_with(123)
        mock_dependencies["telegram"].send_dashboard_button.assert_called_once()
        call_args = mock_dependencies["telegram"].send_dashboard_button.call_args[0]
        assert call_args[0] == 123
        assert "test.jwt.token" in call_args[1]


@pytest.mark.asyncio
async def test_dashboard_in_slash_handler_map(router_service):
    """/dashboard 핸들러가 _slash_handlers에 등록되어 있는지 확인."""
    assert "/dashboard" in router_service._slash_handlers
    assert router_service._slash_handlers["/dashboard"] == router_service._handle_dashboard


@pytest.mark.asyncio
async def test_ask_flow_sends_single_progress_message_and_final_answer(router_service, mock_dependencies):
    """질문 처리 시 진행 메시지 1회 후 최종 답변 전송."""
    mock_dependencies["agent"].answer.return_value = "최종 답변"

    await router_service.route(123, "RAG가 뭐야?")

    assert mock_dependencies["telegram"].send_message.call_count == 2
    first_call = mock_dependencies["telegram"].send_message.call_args_list[0][0]
    second_call = mock_dependencies["telegram"].send_message.call_args_list[1][0]
    assert first_call == (123, "🤖 답변을 생성하는 중입니다...")
    assert second_call == (123, "최종 답변")


@pytest.mark.asyncio
async def test_ask_flow_escapes_html_answer_before_sending(router_service, mock_dependencies):
    """LLM 답변은 Telegram HTML 렌더링 전에 escape된다."""
    mock_dependencies["agent"].answer.return_value = "<b>unsafe</b>"

    await router_service.route(123, "RAG가 뭐야?")

    last_call = mock_dependencies["telegram"].send_message.call_args_list[-1][0]
    assert last_call == (123, "&lt;b&gt;unsafe&lt;/b&gt;")


@pytest.mark.asyncio
async def test_run_safe_error_handling(router_service, mock_dependencies):
    """Test _run_safe handles errors and sends error message."""
    mock_coro = AsyncMock(side_effect=Exception("Test error"))

    await router_service._run_safe(
        123, mock_coro, "arg1", error_msg="Custom error"
    )

    # Should send error message
    mock_dependencies["telegram"].send_message.assert_called_once()
    args = mock_dependencies["telegram"].send_message.call_args[0]
    assert "Custom error" in args[1]
