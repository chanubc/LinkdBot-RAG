"""Phase 4: Dashboard API endpoints.

All endpoints use /me pattern — telegram_id extracted from JWT, never from URL.
"""
from datetime import datetime, timedelta, timezone

import numpy as np
from fastapi import BackgroundTasks, Depends, HTTPException, Query
from fastapi.concurrency import run_in_threadpool
from fastapi.routing import APIRouter
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

from collections import Counter

from app.api.dependencies.auth_di import get_user_repository
from app.api.dependencies.dashboard_auth import get_dashboard_telegram_id
from app.api.dependencies.link_di import get_link_repository, get_openai_client
from app.api.dependencies.rag_di import get_search_usecase
from app.api.dependencies.report_di import get_weekly_report_usecase
from app.application.usecases.search_usecase import SearchUseCase
from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.usecases.generate_weekly_report_usecase import (
    GenerateWeeklyReportUseCase,
)
from app.domain.drift import calculate_drift
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.scoring import (
    calculate_forgetting_score,
    compute_interest_centroid,
    cosine_similarity,
)
from app.infrastructure.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Drift
# ---------------------------------------------------------------------------


@router.get("/drift/me")
async def get_my_drift(
    telegram_id: int = Depends(get_dashboard_telegram_id),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    now = datetime.now(timezone.utc)
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    current_cats = await link_repo.get_categories_by_period(telegram_id, week_ago, now)
    past_cats = await link_repo.get_categories_by_period(
        telegram_id, month_ago, week_ago
    )

    tvd, delta = calculate_drift(current_cats, past_cats)

    # 8-week time series
    weekly_series: list[dict] = []
    for i in range(8, 0, -1):
        week_start = now - timedelta(weeks=i)
        week_end = now - timedelta(weeks=i - 1)
        cats = await link_repo.get_categories_by_period(
            telegram_id, week_start, week_end
        )
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


# ---------------------------------------------------------------------------
# Reactivation
# ---------------------------------------------------------------------------


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
        return {
            "items": [],
            "centroid_source": centroid_source,
            "total": 0,
        }

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
                "created_at": created_at.isoformat()
                if hasattr(created_at, "isoformat")
                else str(created_at),
            }
        )

    scored.sort(key=lambda x: x["score"], reverse=True)
    return {
        "items": scored,
        "centroid_source": centroid_source,
        "total": len(scored),
    }


# ---------------------------------------------------------------------------
# Embeddings (PCA only)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------


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


@router.patch("/links/{link_id}/read")
async def mark_link_read(
    link_id: int,
    telegram_id: int = Depends(get_dashboard_telegram_id),
    db: AsyncSession = Depends(get_db),
    link_repo: ILinkRepository = Depends(get_link_repository),
):
    updated = await link_repo.mark_as_read(link_id, telegram_id)
    await db.commit()
    if not updated:
        raise HTTPException(status_code=404, detail="링크를 찾을 수 없습니다.")
    return {"status": "ok"}


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


# ---------------------------------------------------------------------------
# Stats
# ---------------------------------------------------------------------------


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
    this_week_count = sum(
        1 for l in links
        if l["created_at"] and l["created_at"][:10] >= week_ago
    )
    this_month_count = sum(
        1 for l in links
        if l["created_at"] and l["created_at"][:10] >= month_ago
    )

    cat_counter = Counter(l["category"] for l in links if l["category"])
    top_category = cat_counter.most_common(1)[0][0] if cat_counter else None

    # 월별 저장 수 (최근 6개월)
    monthly: dict[str, int] = {}
    for l in links:
        if l["created_at"]:
            ym = l["created_at"][:7]  # "2026-03"
            monthly[ym] = monthly.get(ym, 0) + 1
    monthly_series = [
        {"month": k, "count": v}
        for k, v in sorted(monthly.items())[-6:]
    ]

    # 카테고리 분포
    category_dist = [
        {"category": cat, "count": cnt}
        for cat, cnt in cat_counter.most_common()
    ]

    # 키워드 Top 20 (keywords는 JSON 배열 문자열)
    import json
    keyword_counter: Counter = Counter()
    for l in links:
        raw = l.get("keywords", "")
        if raw:
            try:
                kws = json.loads(raw) if raw.startswith("[") else [k.strip() for k in raw.split(",")]
                keyword_counter.update(kws)
            except Exception:
                pass
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


# ---------------------------------------------------------------------------
# Search (JWT 기반 — IDOR 방지)
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Report trigger
# ---------------------------------------------------------------------------


@router.post("/report/trigger/me")
async def trigger_my_report(
    background_tasks: BackgroundTasks,
    telegram_id: int = Depends(get_dashboard_telegram_id),
    report_usecase: GenerateWeeklyReportUseCase = Depends(get_weekly_report_usecase),
):
    background_tasks.add_task(report_usecase.execute, telegram_id)
    return {"status": "triggered"}
