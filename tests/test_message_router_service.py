"""Test MessageRouterService refactoring improvements."""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import BackgroundTasks

from app.application.services.message_router_service import MessageRouterService
from app.domain.entities.intent import Intent
from app.application.ports.intent_router_port import RouterOutput as ClassifierOutput


@pytest.fixture
def mock_dependencies():
    """Create mock dependencies for MessageRouterService."""
    return {
        "intent_classifier": AsyncMock(),
        "agent": AsyncMock(),
        "search_uc": AsyncMock(),
        "save_memo_uc": AsyncMock(),
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
    await router_service.route(123, "", None)
    # Should return early without any processing
    assert router_service._intent_classifier.classify.called is False


@pytest.mark.asyncio
async def test_slash_command_with_handler_map(router_service, mock_dependencies):
    """Test slash command dispatch using handler map."""
    # Test /start command
    await router_service.route(123, "/start", None)
    assert mock_dependencies["user_repo"].get_by_telegram_id.called

    # Test /help command
    mock_dependencies["telegram"].reset_mock()
    await router_service.route(123, "/help", None)
    assert mock_dependencies["telegram"].send_help_message.called


@pytest.mark.asyncio
async def test_memo_command_with_payload(router_service, mock_dependencies):
    """Test /memo command with payload."""
    await router_service.route(123, "/memo 오늘 배운 내용", None)

    # Should call save_memo_uc.execute
    assert mock_dependencies["save_memo_uc"].execute.called


@pytest.mark.asyncio
async def test_memo_command_without_payload(router_service, mock_dependencies):
    """Test /memo command without payload shows error message."""
    await router_service.route(123, "/memo", None)

    # Should send error message, not execute save
    mock_dependencies["telegram"].send_message.assert_called_once()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "메모 내용을 입력해주세요" in args[0][1]
    assert mock_dependencies["save_memo_uc"].execute.called is False


@pytest.mark.asyncio
async def test_ask_command_without_payload(router_service, mock_dependencies):
    """Test /ask command without payload."""
    await router_service.route(123, "/ask", None)

    # Should send error message
    mock_dependencies["telegram"].send_message.assert_called_once()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "질문을 입력해주세요" in args[0][1]


@pytest.mark.asyncio
async def test_background_tasks_usage(router_service, mock_dependencies):
    """Test that background_tasks parameter is properly used."""
    bg_tasks = AsyncMock(spec=BackgroundTasks)

    await router_service.route(123, "/memo test content", bg_tasks)

    # Should add task to background_tasks
    bg_tasks.add_task.assert_called()


@pytest.mark.asyncio
async def test_intent_dispatch_with_handler_map(router_service, mock_dependencies):
    """Test intent dispatch using handler map."""
    # Mock intent classification
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.SEARCH,
        query="test query"
    )

    await router_service.route(123, "search something", None)

    # Should dispatch to search handler via handler map
    assert mock_dependencies["search_uc"].execute.called


@pytest.mark.asyncio
async def test_intent_memo_dispatch(router_service, mock_dependencies):
    """Test Intent.MEMO dispatch via handler map."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.MEMO,
        query="test memo"
    )

    await router_service.route(123, "save this memo", None)

    assert mock_dependencies["save_memo_uc"].execute.called


@pytest.mark.asyncio
async def test_intent_ask_dispatch(router_service, mock_dependencies):
    """Test Intent.ASK dispatch via handler map."""
    mock_dependencies["intent_classifier"].classify.return_value = ClassifierOutput(
        intent=Intent.ASK,
        query="test question"
    )

    await router_service.route(123, "ask me something", None)

    assert mock_dependencies["agent"].run.called


@pytest.mark.asyncio
async def test_error_handling_on_classification_failure(router_service, mock_dependencies):
    """Test error handling when intent classification fails."""
    mock_dependencies["intent_classifier"].classify.side_effect = Exception("API Error")

    await router_service.route(123, "some text", None)

    # Should send help message and not crash
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "/help" in args[0][1]


@pytest.mark.asyncio
async def test_error_handling_on_search_failure(router_service, mock_dependencies):
    """Test error handling when search fails."""
    mock_dependencies["search_uc"].execute.side_effect = Exception("Search Error")

    await router_service.route(123, "/search test", None)

    # Should send error message
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args
    assert "오류" in args[0][1]


@pytest.mark.asyncio
async def test_error_handling_on_memo_save_failure(router_service, mock_dependencies):
    """Test error handling when memo save fails."""
    mock_dependencies["save_memo_uc"].execute.side_effect = Exception("DB Error")

    await router_service.route(123, "/memo test", None)

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

    await router_service.route(123, "weird text", None)

    # Should send help message (UNKNOWN not in handler map, so fallback)
    mock_dependencies["telegram"].send_message.assert_called()
    args = mock_dependencies["telegram"].send_message.call_args_list[-1]
    assert "/help" in args[0][1]


@pytest.mark.asyncio
async def test_unknown_slash_command_feedback(router_service, mock_dependencies):
    """Test that unknown slash commands receive feedback (not silent failure)."""
    await router_service.route(123, "/unknown command arg", None)

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
    assert Intent.START in router_service._intent_handlers
    assert Intent.HELP in router_service._intent_handlers

    # Verify intent handlers also point directly to core methods
    assert router_service._intent_handlers[Intent.SEARCH] == router_service._process_search
    assert router_service._intent_handlers[Intent.MEMO] == router_service._process_memo
    assert router_service._intent_handlers[Intent.ASK] == router_service._process_ask
    assert router_service._intent_handlers[Intent.START] == router_service._handle_start
    assert router_service._intent_handlers[Intent.HELP] == router_service._handle_help


@pytest.mark.asyncio
async def test_run_safe_with_background_tasks(router_service, mock_dependencies):
    """Test _run_safe executes in background when BackgroundTasks available."""
    bg_tasks = AsyncMock(spec=BackgroundTasks)
    mock_coro = AsyncMock()

    await router_service._run_safe(123, bg_tasks, mock_coro, "arg1", "arg2")

    # Should add task to background_tasks
    bg_tasks.add_task.assert_called_once()
    # Should NOT execute directly
    assert mock_coro.called is False


@pytest.mark.asyncio
async def test_run_safe_without_background_tasks(router_service, mock_dependencies):
    """Test _run_safe executes directly when BackgroundTasks unavailable."""
    mock_coro = AsyncMock()

    await router_service._run_safe(123, None, mock_coro, "arg1", "arg2")

    # Should execute directly
    mock_coro.assert_called_once_with("arg1", "arg2")


@pytest.mark.asyncio
async def test_run_safe_error_handling(router_service, mock_dependencies):
    """Test _run_safe handles errors and sends error message."""
    mock_coro = AsyncMock(side_effect=Exception("Test error"))

    await router_service._run_safe(
        123, None, mock_coro, "arg1", error_msg="Custom error"
    )

    # Should send error message
    mock_dependencies["telegram"].send_message.assert_called_once()
    args = mock_dependencies["telegram"].send_message.call_args[0]
    assert "Custom error" in args[1]
