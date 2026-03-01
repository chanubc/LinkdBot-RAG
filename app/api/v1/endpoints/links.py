"""링크 리다이렉트 엔드포인트.

GET /api/v1/links/{link_id}/go
  - JWT 인증 (dashboard JWT)
  - is_read 백그라운드 처리
  - 302 redirect → 원본 URL
"""
from fastapi import BackgroundTasks, Depends, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.routing import APIRouter

from app.api.dependencies.dashboard_auth import get_dashboard_telegram_id_from_query
from app.api.dependencies.link_di import get_link_repository
from app.domain.repositories.i_link_repository import ILinkRepository

router = APIRouter()


@router.get("/{link_id}/go", response_class=RedirectResponse)
async def redirect_and_mark_read(
    link_id: int,
    background_tasks: BackgroundTasks,
    telegram_id: int = Depends(get_dashboard_telegram_id_from_query),
    link_repo: ILinkRepository = Depends(get_link_repository),
) -> RedirectResponse:
    """링크 클릭 시 is_read 자동 처리 후 원본 URL로 리다이렉트.

    - URL 조회는 동기적으로 수행 (redirect에 필요)
    - mark_as_read는 응답 후 백그라운드에서 실행 (속도 무영향)
    - user_id 소유권 검증으로 IDOR 방지
    """
    link = await link_repo.get_link_by_id(link_id)

    if link is None:
        raise HTTPException(status_code=404, detail="링크를 찾을 수 없습니다.")

    if link["user_id"] != telegram_id:
        raise HTTPException(status_code=403, detail="접근 권한이 없습니다.")

    if not link["is_read"]:
        background_tasks.add_task(link_repo.mark_as_read, link_id)

    return RedirectResponse(url=link["url"], status_code=302)
