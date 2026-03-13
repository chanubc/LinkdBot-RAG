from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.domain.entities.content_analysis import ContentAnalysis
from app.utils.text import split_markdown


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
async def test_jina_source_embedding_batched_once_for_summary_and_chunks(save_link_usecase, save_link_dependencies):
    """Jina source: summary + chunks가 1회 배치 임베딩으로 처리된다."""
    db = save_link_dependencies["db"]
    user_repo = save_link_dependencies["user_repo"]
    link_repo = save_link_dependencies["link_repo"]
    chunk_repo = save_link_dependencies["chunk_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]

    url = "https://example.com/post"
    content = "# Section One\nhello world from linkdbot"
    summary = "• point one\n• point two"
    raw_chunks = split_markdown(content)

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = (content, "jina", "", "")
    openai.analyze_content.return_value = ContentAnalysis(
        title="테스트 제목",
        summary=summary,
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2]] + [[0.3, 0.4]] * len(raw_chunks)
    link_repo.save_link.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = None
    user_repo.get_by_telegram_id.return_value = None

    await save_link_usecase.execute(telegram_id=111, url=url, memo=None)

    openai.embed.assert_called_once_with([summary] + raw_chunks)

    save_link_kwargs = link_repo.save_link.call_args.kwargs
    assert save_link_kwargs["summary_embedding"] == [0.1, 0.2]

    chunk_repo.save_chunks.assert_called_once_with(
        123,
        list(zip(raw_chunks, [[0.3, 0.4]] * len(raw_chunks))),
    )
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_ai_summary_stored_in_db_and_notion_receives_description_separately(
    save_link_usecase,
    save_link_dependencies,
):
    """ai_summary는 DB summary에 저장되고, Notion은 description/ai_summary를 분리해서 받는다."""
    user_repo = save_link_dependencies["user_repo"]
    link_repo = save_link_dependencies["link_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]
    telegram = save_link_dependencies["telegram"]
    notion = save_link_dependencies["notion"]

    og_description = "OG meta description"
    og_title = "OG Page Title"
    ai_summary = "• point one\n• point two"
    notion_page_url = "https://www.notion.so/workspace/child-page"

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = (og_description, "og", og_description, og_title)
    openai.analyze_content.return_value = ContentAnalysis(
        title="AI Title",
        summary=ai_summary,
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2]]
    link_repo.save_link.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = "secret"
    user_repo.get_by_telegram_id.return_value = SimpleNamespace(notion_database_id="db-123")
    notion.create_database_entry.return_value = notion_page_url

    await save_link_usecase.execute(telegram_id=111, url="https://example.com/post", memo=None)

    # DB에는 ai_summary 저장
    save_link_kwargs = link_repo.save_link.call_args.kwargs
    assert save_link_kwargs["summary"] == ai_summary
    # og_title이 title로 사용됨
    assert save_link_kwargs["title"] == og_title

    # Notion은 description(og_description)과 ai_summary를 분리해서 받음
    notion.create_database_entry.assert_awaited_once_with(
        access_token="secret",
        database_id="db-123",
        title=og_title,
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
        description=og_description,
        ai_summary=ai_summary,
        url="https://example.com/post",
        memo=None,
    )
    telegram.send_link_saved_message.assert_awaited_once()
    assert telegram.send_link_saved_message.await_args.kwargs["notion_url"] == notion_page_url


@pytest.mark.asyncio
async def test_og_source_skips_chunking(save_link_usecase, save_link_dependencies):
    """OG fallback 시 청킹 없이 summary_embedding만 저장된다."""
    link_repo = save_link_dependencies["link_repo"]
    chunk_repo = save_link_dependencies["chunk_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]
    user_repo = save_link_dependencies["user_repo"]

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = ("short description", "og", "short description", "Title")
    openai.analyze_content.return_value = ContentAnalysis(
        title="Title",
        summary="• AI bullet",
        category="Dev",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2]]
    link_repo.save_link.return_value = SimpleNamespace(id=42)
    user_repo.get_decrypted_token.return_value = None
    user_repo.get_by_telegram_id.return_value = None

    await save_link_usecase.execute(telegram_id=111, url="https://example.com", memo=None)

    # summary_embedding만 (청크 없음)
    openai.embed.assert_called_once_with(["• AI bullet"])
    chunk_repo.save_chunks.assert_not_called()


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
