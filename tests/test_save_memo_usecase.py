from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.usecases.save_memo_usecase import SaveMemoUseCase


@pytest.fixture
def save_memo_dependencies() -> dict:
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
def save_memo_usecase(save_memo_dependencies) -> SaveMemoUseCase:
    return SaveMemoUseCase(**save_memo_dependencies)


@pytest.mark.asyncio
async def test_save_memo_forwards_child_page_url_to_completion_message(
    save_memo_usecase,
    save_memo_dependencies,
):
    link_repo = save_memo_dependencies["link_repo"]
    user_repo = save_memo_dependencies["user_repo"]
    notion = save_memo_dependencies["notion"]
    telegram = save_memo_dependencies["telegram"]

    memo = "오늘 배운 내용을 메모합니다."
    notion_page_url = "https://www.notion.so/workspace/memo-child-page"

    link_repo.save_memo.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = "secret"
    user_repo.get_by_telegram_id.return_value = SimpleNamespace(notion_database_id="db-123")
    notion.create_database_entry.return_value = notion_page_url

    await save_memo_usecase.execute(telegram_id=111, memo=memo)

    notion.create_database_entry.assert_awaited_once_with(
        access_token="secret",
        database_id="db-123",
        title=memo[:50],
        category="Memo",
        keywords=[],
        summary="",
        url=None,
        memo=memo,
    )
    assert telegram.send_message.await_args_list[-1].args == (
        111,
        f"✅ 메모 저장 완료!\n\n📓 Notion: {notion_page_url}",
    )


@pytest.mark.asyncio
async def test_save_memo_without_notion_credentials_omits_notion_link(
    save_memo_usecase,
    save_memo_dependencies,
):
    link_repo = save_memo_dependencies["link_repo"]
    user_repo = save_memo_dependencies["user_repo"]
    notion = save_memo_dependencies["notion"]
    telegram = save_memo_dependencies["telegram"]

    link_repo.save_memo.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = None
    user_repo.get_by_telegram_id.return_value = None

    await save_memo_usecase.execute(telegram_id=111, memo="간단 메모")

    notion.create_database_entry.assert_not_called()
    assert telegram.send_message.await_args_list[-1].args == (111, "✅ 메모 저장 완료!")
