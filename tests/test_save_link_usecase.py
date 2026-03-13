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
    semantic_summary = "링크드봇은 지식 관리 도구다. 섹션 원을 다룬다."
    raw_chunks = split_markdown(content)

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = (content, "jina", "", "")
    openai.analyze_content.return_value = ContentAnalysis(
        title="테스트 제목",
        semantic_summary=semantic_summary,
        display_points=["point one", "point two"],
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2]] + [[0.3, 0.4]] * len(raw_chunks)
    link_repo.save_link.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = None
    user_repo.get_by_telegram_id.return_value = None

    await save_link_usecase.execute(telegram_id=111, url=url, memo=None)

    openai.embed.assert_called_once_with([semantic_summary] + raw_chunks)

    save_link_kwargs = link_repo.save_link.call_args.kwargs
    assert save_link_kwargs["summary_embedding"] == [0.1, 0.2]

    chunk_repo.save_chunks.assert_called_once_with(
        123,
        list(zip(raw_chunks, [[0.3, 0.4]] * len(raw_chunks))),
    )
    db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_semantic_summary_stored_in_db_display_points_sent_to_notion(
    save_link_usecase,
    save_link_dependencies,
):
    """semantic_summary는 DB summary에, display_points는 bullet 포맷으로 Notion ai_summary에 전달된다."""
    user_repo = save_link_dependencies["user_repo"]
    link_repo = save_link_dependencies["link_repo"]
    openai = save_link_dependencies["openai"]
    scraper = save_link_dependencies["scraper"]
    telegram = save_link_dependencies["telegram"]
    notion = save_link_dependencies["notion"]

    og_description = "OG meta description"
    og_title = "OG Page Title"
    semantic_summary = "하나증권은 2026 신입 공채를 실시한다. AI 직무 포함 다수 부문 채용 예정이다."
    display_points = ["AI 직무 포함 신입 공채", "지원 자격: 학사 이상", "마감: 2026-03-31"]
    expected_ai_summary = "• AI 직무 포함 신입 공채\n• 지원 자격: 학사 이상\n• 마감: 2026-03-31"
    notion_page_url = "https://www.notion.so/workspace/child-page"

    link_repo.exists_by_user_and_url.return_value = False
    scraper.scrape.return_value = (og_description, "og", og_description, og_title)
    openai.analyze_content.return_value = ContentAnalysis(
        title="AI Title",
        semantic_summary=semantic_summary,
        display_points=display_points,
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2]]
    link_repo.save_link.return_value = SimpleNamespace(id=123)
    user_repo.get_decrypted_token.return_value = "secret"
    user_repo.get_by_telegram_id.return_value = SimpleNamespace(notion_database_id="db-123")
    notion.create_database_entry.return_value = notion_page_url

    await save_link_usecase.execute(telegram_id=111, url="https://example.com/post", memo=None)

    # DB에는 semantic_summary 저장
    save_link_kwargs = link_repo.save_link.call_args.kwargs
    assert save_link_kwargs["summary"] == semantic_summary
    # og_title이 title로 사용됨
    assert save_link_kwargs["title"] == og_title

    # Notion은 description(og_description)과 display_points 기반 bullet을 분리해서 받음
    notion.create_database_entry.assert_awaited_once_with(
        access_token="secret",
        database_id="db-123",
        title=og_title,
        category="AI",
        keywords=["a", "b", "c", "d", "e"],
        description=og_description,
        ai_summary=expected_ai_summary,
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
        semantic_summary="이 링크는 짧은 설명을 담고 있다.",
        display_points=["AI 관련 내용"],
        category="Dev",
        keywords=["a", "b", "c", "d", "e"],
    )
    openai.embed.return_value = [[0.1, 0.2]]
    link_repo.save_link.return_value = SimpleNamespace(id=42)
    user_repo.get_decrypted_token.return_value = None
    user_repo.get_by_telegram_id.return_value = None

    await save_link_usecase.execute(telegram_id=111, url="https://example.com", memo=None)

    # summary_embedding만 (청크 없음) — semantic_summary 기반
    openai.embed.assert_called_once_with(["이 링크는 짧은 설명을 담고 있다."])
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
