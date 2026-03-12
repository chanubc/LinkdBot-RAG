from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.domain.entities.content_analysis import ContentAnalysis
from app.utils.text import split_chunks


@pytest.fixture
def save_link_dependencies() -> dict:
    return {
        "db": AsyncMock(),
        "user_repo": AsyncMock(),
        "link_repo": AsyncMock(),
        "chunk_repo": AsyncMock(),
        "openai": AsyncMock(),
        "scraper": AsyncMock(),
        "telegram": AsyncMock(),
        "notion": AsyncMock(),
    }


@pytest.fixture
def save_link_usecase(save_link_dependencies) -> SaveLinkUseCase:
    return SaveLinkUseCase(**save_link_dependencies)


@pytest.mark.asyncio
async def test_duplicate_url_short_circuit_without_llm_calls(save_link_usecase, save_link_dependencies):
    link_repo = save_link_dependencies["link_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]
    telegram = save_link_dependencies["telegram"]

    link_repo.exists_by_user_and_url.return_value = True

    await save_link_usecase.execute(telegram_id=111, url="https://example.com", memo=None)

    scraper.scrape.assert_not_called()
    openai.analyze_content.assert_not_called()
    openai.embed.assert_not_called()
    link_repo.save_link.assert_not_called()
    telegram.send_message.assert_called_once_with(111, "⚠️ 이미 저장된 링크입니다.")


@pytest.mark.asyncio
async def test_embedding_batched_once_for_summary_and_chunks(save_link_usecase, save_link_dependencies):
    db = save_link_dependencies["db"]
    user_repo = save_link_dependencies["user_repo"]
    link_repo = save_link_dependencies["link_repo"]
    chunk_repo = save_link_dependencies["chunk_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]

    url = "https://example.com/post"
    content = "hello world from linkdbot"
    summary = "요약 텍스트"
    raw_chunks = split_chunks(content)

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = (content, "og", "")
    openai.analyze_content.return_value = ContentAnalysis(
        title="테스트 제목",
        summary=summary,
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
    link_repo.save_link.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = None
    user_repo.get_by_telegram_id.return_value = None

    await save_link_usecase.execute(telegram_id=111, url=url, memo=None)

    openai.embed.assert_called_once_with([summary] + raw_chunks)

    save_link_kwargs = link_repo.save_link.call_args.kwargs
    assert save_link_kwargs["summary_embedding"] == [0.1, 0.2]

    chunk_repo.save_chunks.assert_called_once_with(
        123,
        list(zip(raw_chunks, [[0.3, 0.4]])),
    )
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_og_description_prioritized_and_child_page_url_forwarded(
    save_link_usecase,
    save_link_dependencies,
):
    user_repo = save_link_dependencies["user_repo"]
    link_repo = save_link_dependencies["link_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]
    telegram = save_link_dependencies["telegram"]
    notion = save_link_dependencies["notion"]

    content = "hello world from linkdbot"
    og_description = "OG description wins"
    notion_page_url = "https://www.notion.so/workspace/child-page"

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = (content, "og", og_description)
    openai.analyze_content.return_value = ContentAnalysis(
        title="테스트 제목",
        summary="LLM fallback summary",
        category="AI",
        keywords=["a", "b"],
    )
    openai.embed.return_value = [[0.1, 0.2], [0.3, 0.4]]
    link_repo.save_link.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = "secret"
    user_repo.get_by_telegram_id.return_value = SimpleNamespace(notion_database_id="db-123")
    notion.create_database_entry.return_value = notion_page_url

    await save_link_usecase.execute(telegram_id=111, url="https://example.com/post", memo=None)

    save_link_kwargs = link_repo.save_link.call_args.kwargs
    assert save_link_kwargs["summary"] == og_description

    notion.create_database_entry.assert_awaited_once_with(
        access_token="secret",
        database_id="db-123",
        title="테스트 제목",
        category="AI",
        keywords=["a", "b"],
        summary=og_description,
        content=content,
        url="https://example.com/post",
        memo=None,
    )
    telegram.send_link_saved_message.assert_awaited_once()
    assert telegram.send_link_saved_message.await_args.kwargs["notion_url"] == notion_page_url


@pytest.mark.asyncio
async def test_url_normalized_before_duplicate_check(save_link_usecase, save_link_dependencies):
    """트래킹 파라미터가 제거된 URL로 중복 체크가 수행되어야 한다."""
    link_repo = save_link_dependencies["link_repo"]
    link_repo.exists_by_user_and_url.return_value = True

    dirty_url = "https://www.threads.com/@user/post/ABC?xmt=SESSION1&slof=1"
    clean_url = "https://www.threads.com/@user/post/ABC"

    await save_link_usecase.execute(telegram_id=111, url=dirty_url, memo=None)

    link_repo.exists_by_user_and_url.assert_called_once_with(111, clean_url)


@pytest.mark.asyncio
async def test_url_without_tracking_params_unchanged(save_link_usecase, save_link_dependencies):
    """트래킹 파라미터 없는 URL은 그대로 중복 체크에 사용된다."""
    link_repo = save_link_dependencies["link_repo"]
    link_repo.exists_by_user_and_url.return_value = True

    url = "https://example.com/article?id=42"
    await save_link_usecase.execute(telegram_id=111, url=url, memo=None)

    link_repo.exists_by_user_and_url.assert_called_once_with(111, url)
