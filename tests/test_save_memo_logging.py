from types import SimpleNamespace
from unittest.mock import AsyncMock
from unittest.mock import patch

import pytest

from app.application.usecases.save_memo_usecase import SaveMemoUseCase


@pytest.fixture
def save_memo_dependencies_for_logging() -> dict:
    return {
        "db": AsyncMock(),
        "user_repo": AsyncMock(),
        "link_repo": AsyncMock(),
        "chunk_repo": AsyncMock(),
        "openai": AsyncMock(),
        "telegram": AsyncMock(),
        "notion": AsyncMock(),
    }


@pytest.fixture
def save_memo_usecase_for_logging(save_memo_dependencies_for_logging) -> SaveMemoUseCase:
    return SaveMemoUseCase(**save_memo_dependencies_for_logging)


@pytest.mark.asyncio
async def test_save_memo_logs_notion_failure_and_still_completes(
    save_memo_usecase_for_logging,
    save_memo_dependencies_for_logging,
):
    link_repo = save_memo_dependencies_for_logging["link_repo"]
    user_repo = save_memo_dependencies_for_logging["user_repo"]
    notion = save_memo_dependencies_for_logging["notion"]
    telegram = save_memo_dependencies_for_logging["telegram"]

    link_repo.save_memo.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = "secret"
    user_repo.get_by_telegram_id.return_value = SimpleNamespace(notion_database_id="db-123")
    notion.create_database_entry.side_effect = RuntimeError("memo notion failed")

    with patch("app.application.usecases.save_memo_usecase.logger.exception") as mock_exception:
        await save_memo_usecase_for_logging.execute(telegram_id=111, memo="simple memo")

    mock_exception.assert_called_once()
    assert "telegram_id=111" in mock_exception.call_args.args[0]
    assert "db-123" in mock_exception.call_args.args[0]
    assert telegram.send_message.await_args_list[-1].args == (111, "✅ 메모 저장 완료!")
