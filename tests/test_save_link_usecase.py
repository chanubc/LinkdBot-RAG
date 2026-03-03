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
    scraper.scrape.return_value = (content, "og")
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
