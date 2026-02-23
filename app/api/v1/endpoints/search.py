from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_search_service
from app.services.search_service import SearchService

router = APIRouter()


@router.get("")
async def semantic_search(
    telegram_id: int = Query(...),
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    search_service: SearchService = Depends(get_search_service),
):
    """시맨틱 검색 — 사용자의 저장된 링크에서 유사 청크 반환."""
    results = await search_service.search(telegram_id, q, top_k)
    return {"query": q, "results": results}
