from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.application.usecases.recall_memo_usecase import RecallMemoUseCase


@pytest.mark.asyncio
async def test_recall_memo_usecase_queries_repo_with_time_filter():
    link_repo = AsyncMock()
    memo = AsyncMock()
    memo.title = "어제 메모"
    memo.memo = "테스트"
    memo.created_at = datetime(2026, 3, 10, 3, 0, tzinfo=timezone.utc)
    link_repo.get_memos_by_period.return_value = [memo]

    usecase = RecallMemoUseCase(link_repo)
    results = await usecase.execute(telegram_id=1, query="", time_filter="yesterday")

    assert len(results) == 1
    assert results[0]["title"] == "어제 메모"
    assert results[0]["similarity"] == 1.0
    called = link_repo.get_memos_by_period.call_args.kwargs
    assert called["user_id"] == 1
    assert called["query"] == ""
    assert called["limit"] == 5
    assert called["end"] > called["start"]


def test_to_period_defaults_to_recent_window():
    start, end = RecallMemoUseCase._to_period(None)
    assert end > start
    assert (end - start).days >= 29
