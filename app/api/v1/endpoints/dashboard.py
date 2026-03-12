"""Phase 4: Dashboard API endpoints.

All endpoints use /me pattern — telegram_id extracted from JWT, never from URL.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import json

import numpy as np
from fastapi import Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.routing import APIRouter
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_di import get_user_repository
from app.api.dependencies.dashboard_auth import get_dashboard_telegram_id
from app.api.dependencies.link_di import get_link_repository, get_openai_client
from app.api.dependencies.rag_di import get_search_usecase
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.usecases.search_usecase import SearchUseCase
from app.domain.drift import calculate_drift
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.scoring import (
    calculate_forgetting_score,
    compute_interest_centroid,
    cosine_similarity,
)
from app.infrastructure.database import get_db

router = APIRouter()
_GRAPH_LINK_LIMIT = 150


@router.get("/auth/me")
async def get_my_info(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    user_repo: IUserRepository = Depends(get_user_repository),
):
    user = await user_repo.get_by_telegram_id(telegram_id)
    return {
        "telegram_id": telegram_id,
        "first_name": user.first_name if user else None,
    }


@router.get("/drift/me")
async def get_my_drift(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    current_cats = await link_repo.get_categories_by_period(telegram_id, week_ago, now)
    past_cats = await link_repo.get_categories_by_period(telegram_id, month_ago, week_ago)

    tvd, delta = calculate_drift(current_cats, past_cats)

    weekly_series: list[dict] = []
    for i in range(8, 0, -1):
        week_start = now - timedelta(weeks=i)
        week_end = now - timedelta(weeks=i - 1)
        cats = await link_repo.get_categories_by_period(telegram_id, week_start, week_end)
        from app.domain.drift import calculate_category_distribution

        dist = calculate_category_distribution(cats)
        weekly_series.append(
            {
                "week_start": week_start.date().isoformat(),
                "week_end": week_end.date().isoformat(),
                "distribution": dist,
                "total": len(cats),
            }
        )

    return {
        "tvd": tvd,
        "delta": delta,
        "current_distribution": _dist(current_cats),
        "past_distribution": _dist(past_cats),
        "weekly_series": weekly_series,
    }


def _dist(cats: list[str]) -> dict[str, float]:
    from app.domain.drift import calculate_category_distribution

    return calculate_category_distribution(cats)


@router.get("/reactivation/me")
async def get_my_reactivation(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
    openai: AIAnalysisPort = Depends(get_openai_client),
    query: str | None = None,
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)

    if query:
        embeddings = await openai.embed([query])
        centroid = embeddings[0] if embeddings else None
        centroid_source = "keyword"
    else:
        recent_embeddings = await link_repo.get_summary_embeddings_by_period(
            telegram_id, week_ago, now
        )
        centroid = compute_interest_centroid(recent_embeddings)
        centroid_source = "recent_activity"

    candidates = await link_repo.get_reactivation_candidates(
        telegram_id, older_than_days=3
    )

    if not centroid or not candidates:
        return {"items": [], "centroid_source": centroid_source, "total": 0}

    scored = []
    for c in candidates:
        emb = c.get("summary_embedding")
        created_at = c.get("created_at")
        if emb is None or created_at is None:
            continue
        similarity = float((cosine_similarity(emb, centroid) + 1) / 2)
        recency = float(calculate_forgetting_score(created_at))
        score = similarity * 0.6 + recency * 0.4
        scored.append(
            {
                "id": c["link_id"],
                "title": c["title"],
                "url": c["url"],
                "category": c["category"],
                "summary": c["summary"],
                "similarity": round(similarity, 4),
                "recency": round(recency, 4),
                "score": round(score, 4),
                "created_at": created_at.isoformat() if hasattr(created_at, "isoformat") else str(created_at),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "items": scored,
        "centroid_source": centroid_source,
        "total": len(scored),
    }


@router.get("/embeddings/me")
async def get_my_embeddings(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    links = await link_repo.get_links_with_embeddings(telegram_id, limit=300)
    if len(links) < 3:
        return {"items": [], "explained_variance": None}

    def _compute_pca():
        emb = np.array([l["summary_embedding"] for l in links])
        scaler = StandardScaler()
        pca = PCA(n_components=2)
        c = pca.fit_transform(scaler.fit_transform(emb))
        return c, float(sum(pca.explained_variance_ratio_))

    coords, explained_variance = await run_in_threadpool(_compute_pca)

    items = [
        {
            "id": links[i]["id"],
            "title": links[i]["title"],
            "category": links[i]["category"],
            "x": float(coords[i, 0]),
            "y": float(coords[i, 1]),
        }
        for i in range(len(links))
    ]
    return {"items": items, "explained_variance": explained_variance}


@router.get("/graph/me")
async def get_my_graph(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    links = await link_repo.get_all_links_with_metadata(telegram_id, limit=_GRAPH_LINK_LIMIT)
    return _build_graph_payload(links)


@router.get("/links/me")
async def get_my_links(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
    is_read: bool | None = None,
    category: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
):
    links = await link_repo.get_all_links_with_metadata(telegram_id, limit=500)

    if is_read is not None:
        links = [l for l in links if l["is_read"] == is_read]
    if category:
        links = [l for l in links if l["category"] == category]

    total = len(links)
    start = (page - 1) * page_size
    end = start + page_size
    return {
        "items": links[start:end],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.delete("/links/{link_id}")
async def delete_link(
    link_id: int,
    telegram_id: int = Depends(get_dashboard_telegram_id),
    db: AsyncSession = Depends(get_db),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    deleted = await link_repo.delete_link(link_id, telegram_id)
    await db.commit()
    if not deleted:
        raise HTTPException(status_code=404, detail="링크를 찾을 수 없습니다.")
    return {"status": "ok"}


@router.get("/stats/me")
async def get_my_stats(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    links = await link_repo.get_all_links_with_metadata(telegram_id, limit=500)
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).date().isoformat()
    month_ago = (now - timedelta(days=30)).date().isoformat()

    total = len(links)
    read_count = sum(1 for l in links if l["is_read"])
    this_week_count = sum(1 for l in links if l["created_at"] and l["created_at"][:10] >= week_ago)
    this_month_count = sum(1 for l in links if l["created_at"] and l["created_at"][:10] >= month_ago)

    cat_counter = Counter(l["category"] for l in links if l["category"])
    top_category = cat_counter.most_common(1)[0][0] if cat_counter else None

    monthly: dict[str, int] = {}
    for l in links:
        if l["created_at"]:
            ym = l["created_at"][:7]
            monthly[ym] = monthly.get(ym, 0) + 1
    monthly_series = [{"month": k, "count": v} for k, v in sorted(monthly.items())[-6:]]

    category_dist = [
        {"category": cat, "count": cnt}
        for cat, cnt in cat_counter.most_common()
    ]

    keyword_counter: Counter = Counter()
    for l in links:
        keyword_counter.update(_parse_keywords(l.get("keywords", "")))

    top_keywords = [
        {"keyword": kw, "count": cnt}
        for kw, cnt in keyword_counter.most_common(20)
        if kw
    ]

    return {
        "total": total,
        "read_count": read_count,
        "unread_count": total - read_count,
        "read_ratio": round(read_count / total, 3) if total > 0 else 0.0,
        "this_week_count": this_week_count,
        "this_month_count": this_month_count,
        "top_category": top_category,
        "monthly_series": monthly_series,
        "category_dist": category_dist,
        "top_keywords": top_keywords,
    }


@router.get("/search/me")
async def search_my_links(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    search_usecase: SearchUseCase = Depends(get_search_usecase),
    q: str = "",
    top_k: int = 10,
):
    if not q.strip():
        return {"query": q, "results": []}
    results = await search_usecase.execute(telegram_id, q, top_k)
    return {"query": q, "results": results}


def _build_graph_payload(links: list[dict]) -> dict:
    if not links:
        return {"nodes": [], "edges": [], "meta": {"link_count": 0, "category_count": 0}}

    category_counts = Counter(link.get("category") or "Uncategorized" for link in links)
    nodes: list[dict] = []
    edges: list[dict] = []

    for category, count in sorted(category_counts.items()):
        category_id = f"category:{category}"
        nodes.append(
            {
                "id": category_id,
                "type": "category",
                "label": category,
                "title": category,
                "category": category,
                "size": 22 + (count * 2),
            }
        )

    for link in links:
        category = link.get("category") or "Uncategorized"
        category_id = f"category:{category}"
        link_id = f"link:{link['id']}"
        title = link.get("title") or "제목 없음"
        nodes.append(
            {
                "id": link_id,
                "type": "link",
                "label": _truncate_label(title, 22),
                "title": title,
                "category": category,
                "url": link.get("url"),
                "size": 10,
                "is_read": link.get("is_read", False),
                "created_at": link.get("created_at"),
            }
        )
        edges.append({"source": category_id, "target": link_id})

    return {
        "nodes": nodes,
        "edges": edges,
        "meta": {
            "link_count": len(links),
            "category_count": len(category_counts),
        },
    }


def _truncate_label(text: str, limit: int) -> str:
    return text if len(text) <= limit else f"{text[:limit - 1]}…"


def _parse_keywords(raw: str) -> list[str]:
    if not raw:
        return []
    try:
        if raw.startswith("["):
            return [keyword.strip() for keyword in json.loads(raw) if keyword and str(keyword).strip()]
        return [keyword.strip() for keyword in raw.split(",") if keyword.strip()]
    except Exception:
        return []
