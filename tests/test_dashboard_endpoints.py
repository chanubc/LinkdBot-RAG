from unittest.mock import AsyncMock

import pytest

from app.api.v1.endpoints.dashboard import _build_graph_payload, get_my_graph, get_my_stats


@pytest.mark.asyncio
async def test_get_my_graph_groups_links_under_categories() -> None:
    link_repo = AsyncMock()
    link_repo.get_all_links_with_metadata.return_value = [
        {
            "id": 1,
            "title": "Graph RAG Patterns",
            "url": "https://example.com/rag",
            "category": "AI",
            "keywords": '["rag", "graph"]',
            "is_read": False,
            "created_at": "2026-03-10T10:00:00+00:00",
            "summary": "summary",
        },
        {
            "id": 2,
            "title": "Career Notes",
            "url": "https://example.com/career",
            "category": "Career",
            "keywords": '["career"]',
            "is_read": True,
            "created_at": "2026-03-09T10:00:00+00:00",
            "summary": "summary",
        },
    ]

    result = await get_my_graph(telegram_id=123, link_repo=link_repo)

    assert result["meta"] == {"link_count": 2, "category_count": 2}
    assert {node["id"] for node in result["nodes"] if node["type"] == "category"} == {
        "category:AI",
        "category:Career",
    }
    assert result["edges"] == [
        {"source": "category:AI", "target": "link:1"},
        {"source": "category:Career", "target": "link:2"},
    ]


@pytest.mark.asyncio
async def test_get_my_stats_parses_json_and_csv_keywords() -> None:
    link_repo = AsyncMock()
    link_repo.get_all_links_with_metadata.return_value = [
        {
            "id": 1,
            "title": "A",
            "url": "https://example.com/a",
            "category": "AI",
            "keywords": '["rag", "agent"]',
            "is_read": True,
            "created_at": "2026-03-10T10:00:00+00:00",
            "summary": "summary",
        },
        {
            "id": 2,
            "title": "B",
            "url": "https://example.com/b",
            "category": "AI",
            "keywords": "rag, graph",
            "is_read": False,
            "created_at": "2026-02-01T10:00:00+00:00",
            "summary": "summary",
        },
    ]

    result = await get_my_stats(telegram_id=123, link_repo=link_repo)

    assert result["total"] == 2
    assert result["read_count"] == 1
    assert result["top_category"] == "AI"
    assert result["top_keywords"][:3] == [
        {"keyword": "rag", "count": 2},
        {"keyword": "agent", "count": 1},
        {"keyword": "graph", "count": 1},
    ]


def test_build_graph_payload_truncates_long_titles() -> None:
    payload = _build_graph_payload(
        [
            {
                "id": 99,
                "title": "A very long article title that should be shortened",
                "url": None,
                "category": "AI",
                "is_read": False,
                "created_at": None,
            }
        ]
    )

    link_node = next(node for node in payload["nodes"] if node["type"] == "link")
    assert link_node["label"].endswith("…")
    assert len(link_node["label"]) == 22
