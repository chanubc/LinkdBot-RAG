from fastapi import APIRouter, Depends, Query

from app.api.dependencies.rag_di import get_search_usecase
from app.application.usecases.search_usecase import SearchUseCase

router = APIRouter()


@router.get("")
async def semantic_search(
    telegram_id: int = Query(...),
    q: str = Query(..., min_length=1),
    top_k: int = Query(default=5, ge=1, le=20),
    search_usecase: SearchUseCase = Depends(get_search_usecase),
):
    """시맨틱 검색 — 사용자의 저장된 링크에서 유사 청크 반환."""
    results = await search_usecase.execute(telegram_id, q, top_k)
    return {"query": q, "results": results}
