"""GenerateWeeklyReportUseCase unit tests."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.application.usecases.generate_weekly_report_usecase import (
    GenerateWeeklyReportUseCase,
    _build_report_message,
)


def _make_user(telegram_id: int) -> MagicMock:
    user = MagicMock()
    user.telegram_id = telegram_id
    return user


def _make_candidate(
    link_id: int = 1,
    title: str = "Test Title",
    summary: str = "Test summary",
    category: str = "AI",
    url: str = "https://example.com",
    embedding: list[float] | None = None,
    created_at: datetime | None = None,
) -> dict:
    return {
        "link_id": link_id,
        "summary_embedding": embedding or [0.1, 0.2, 0.3],
        "created_at": created_at or datetime(2024, 1, 1, tzinfo=timezone.utc),
        "title": title,
        "summary": summary,
        "category": category,
        "url": url,
    }


@pytest.fixture
def mock_db() -> AsyncMock:
    db = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    return db


@pytest.fixture
def mock_dependencies(mock_db) -> dict:
    return {
        "db": mock_db,
        "user_repo": AsyncMock(),
        "link_repo": AsyncMock(),
        "rec_repo": AsyncMock(),
        "openai": AsyncMock(),
        "telegram": AsyncMock(),
    }


@pytest.fixture
def usecase(mock_dependencies) -> GenerateWeeklyReportUseCase:
    return GenerateWeeklyReportUseCase(**mock_dependencies)


@pytest.mark.asyncio
async def test_happy_path(usecase, mock_dependencies, mock_db):
    lr = mock_dependencies["link_repo"]
    rr = mock_dependencies["rec_repo"]
    openai = mock_dependencies["openai"]
    telegram = mock_dependencies["telegram"]

    lr.get_categories_by_period.return_value = ["AI", "Dev", "AI", "Career"]
    lr.get_summary_embeddings_by_period.return_value = [[0.1, 0.2, 0.3]]
    lr.get_reactivation_candidates.return_value = [_make_candidate()]
    rr.get_recently_recommended_link_ids.return_value = []
    openai.generate_briefing.return_value = "주간 브리핑 내용"

    await usecase.execute(111)

    openai.generate_briefing.assert_called_once()
    telegram.send_weekly_report.assert_called_once()
    rr.record.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_no_embeddings_early_return(usecase, mock_dependencies, mock_db):
    lr = mock_dependencies["link_repo"]
    openai = mock_dependencies["openai"]
    telegram = mock_dependencies["telegram"]

    lr.get_categories_by_period.return_value = []
    lr.get_summary_embeddings_by_period.return_value = []
    lr.get_all_summary_embeddings.return_value = []

    await usecase.execute(111)

    openai.generate_briefing.assert_not_called()
    telegram.send_weekly_report.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_no_candidates_early_return(usecase, mock_dependencies, mock_db):
    lr = mock_dependencies["link_repo"]
    rr = mock_dependencies["rec_repo"]
    openai = mock_dependencies["openai"]
    telegram = mock_dependencies["telegram"]

    lr.get_categories_by_period.return_value = ["AI", "Dev", "AI", "Career"]
    lr.get_summary_embeddings_by_period.return_value = [[0.1, 0.2, 0.3]]
    rr.get_recently_recommended_link_ids.return_value = []
    lr.get_reactivation_candidates.return_value = []

    await usecase.execute(111)

    openai.generate_briefing.assert_not_called()
    telegram.send_weekly_report.assert_not_called()
    mock_db.commit.assert_not_called()


@pytest.mark.asyncio
async def test_execute_for_all_users(usecase, mock_dependencies):
    users = [_make_user(111), _make_user(222), _make_user(333)]
    mock_dependencies["user_repo"].get_all_users.return_value = users

    with patch.object(usecase, "execute", new=AsyncMock()) as mock_execute:
        await usecase.execute_for_all_users()

    assert mock_execute.call_count == 3
    called_ids = [call.args[0] for call in mock_execute.call_args_list]
    assert called_ids == [111, 222, 333]


@pytest.mark.asyncio
async def test_error_isolation(usecase, mock_dependencies, mock_db):
    users = [_make_user(111), _make_user(222), _make_user(333)]
    mock_dependencies["user_repo"].get_all_users.return_value = users

    async def _execute_side_effect(user_id: int) -> None:
        if user_id == 222:
            raise RuntimeError("DB error for user 222")

    with patch.object(usecase, "execute", new=AsyncMock(side_effect=_execute_side_effect)):
        await usecase.execute_for_all_users()

    mock_db.rollback.assert_called_once()


@pytest.mark.asyncio
async def test_excluded_ids_passed_to_candidates(usecase, mock_dependencies):
    lr = mock_dependencies["link_repo"]
    rr = mock_dependencies["rec_repo"]

    lr.get_categories_by_period.return_value = ["AI", "Dev", "AI", "Career"]
    lr.get_summary_embeddings_by_period.return_value = [[0.1, 0.2, 0.3]]
    rr.get_recently_recommended_link_ids.return_value = [10, 20]
    lr.get_reactivation_candidates.return_value = []

    await usecase.execute(111)

    call_kwargs = lr.get_reactivation_candidates.call_args.kwargs
    assert call_kwargs["excluded_ids"] == [10, 20]


@pytest.mark.asyncio
async def test_recent_embeddings_empty_uses_all_fallback(usecase, mock_dependencies):
    lr = mock_dependencies["link_repo"]
    rr = mock_dependencies["rec_repo"]

    lr.get_categories_by_period.return_value = []
    lr.get_summary_embeddings_by_period.return_value = []
    lr.get_all_summary_embeddings.return_value = [[0.5, 0.5, 0.5]]
    rr.get_recently_recommended_link_ids.return_value = []
    lr.get_reactivation_candidates.return_value = []

    await usecase.execute(111)

    lr.get_all_summary_embeddings.assert_called_once_with(111)


@pytest.mark.asyncio
async def test_drift_skipped_when_few_categories(usecase, mock_dependencies, mock_db):
    lr = mock_dependencies["link_repo"]
    rr = mock_dependencies["rec_repo"]
    openai = mock_dependencies["openai"]
    telegram = mock_dependencies["telegram"]

    lr.get_categories_by_period.return_value = ["AI", "Dev"]
    lr.get_summary_embeddings_by_period.return_value = [[0.1, 0.2, 0.3]]
    rr.get_recently_recommended_link_ids.return_value = []
    lr.get_reactivation_candidates.return_value = [_make_candidate()]
    openai.generate_briefing.return_value = "브리핑"

    await usecase.execute(111)

    openai.generate_briefing.assert_called_once()
    telegram.send_weekly_report.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_send_weekly_report_parameters(usecase, mock_dependencies):
    lr = mock_dependencies["link_repo"]
    rr = mock_dependencies["rec_repo"]
    openai = mock_dependencies["openai"]
    telegram = mock_dependencies["telegram"]

    candidate = _make_candidate(link_id=42, title="중요한 링크", url="https://test.com")
    lr.get_categories_by_period.return_value = ["AI", "Dev", "AI", "Career"]
    lr.get_summary_embeddings_by_period.return_value = [[0.1, 0.2, 0.3]]
    rr.get_recently_recommended_link_ids.return_value = []
    lr.get_reactivation_candidates.return_value = [candidate]
    openai.generate_briefing.return_value = "이번 주 브리핑 텍스트"

    await usecase.execute(999)

    telegram.send_weekly_report.assert_called_once()
    call_kwargs = telegram.send_weekly_report.call_args.kwargs
    assert call_kwargs["chat_id"] == 999
    assert call_kwargs["link_id"] == 42
    assert "이번 주 지식 리포트" in call_kwargs["text"]
    assert "이번 주 브리핑 텍스트" in call_kwargs["text"]


def test_build_report_message_uses_well_formed_html_labels():
    candidate = _make_candidate(title="중요한 링크", url="https://test.com")

    message = _build_report_message("이번 주 브리핑 텍스트", candidate)

    assert "<b>이번 주 지식 리포트</b>" in message
    assert "<b>다시 보기 추천</b>" in message
    assert "<b>중요한 링크</b>" in message
    assert message.count("<b>") == message.count("</b>")
