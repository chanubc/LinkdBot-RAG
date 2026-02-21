from fastapi import APIRouter, Depends, Query

from app.api.dependencies import get_link_service
from app.services.link_service import LinkService

router = APIRouter()


@router.get("")
async def semantic_search(
    telegram_id: int = Query(...),
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    link_service: LinkService = Depends(get_link_service),
):
    """시맨틱 검색 — 사용자의 저장된 링크에서 유사 청크 반환."""
    results = await link_service.search(telegram_id, q, top_k)
    return {"query": q, "results": results}
