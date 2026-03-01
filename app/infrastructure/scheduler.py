"""APScheduler 기반 주간 리포트 스케줄러.

매주 월요일 09:00 KST (= 00:00 UTC) 실행.
FastAPI lifespan에서 start/stop.
"""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.core.logger import logger


def create_scheduler() -> AsyncIOScheduler:
    """AsyncIOScheduler 인스턴스 생성 및 주간 리포트 Job 등록."""
    scheduler = AsyncIOScheduler(timezone="Asia/Seoul")
    scheduler.add_job(
        _run_weekly_report,
        trigger=CronTrigger(day_of_week="mon", hour=9, minute=0, timezone="Asia/Seoul"),
        id="weekly_report",
        replace_existing=True,
        name="Weekly Knowledge Report",
    )
    return scheduler


async def _run_weekly_report() -> None:
    """스케줄러 콜백 — 새 DB 세션으로 GenerateWeeklyReportUseCase 실행."""
    from app.api.dependencies.report_di import build_weekly_report_usecase
    from app.infrastructure.database import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        try:
            usecase = build_weekly_report_usecase(session)
            await usecase.execute_for_all_users()
            logger.info("Weekly report job completed successfully")
        except Exception as exc:
            logger.exception(f"Weekly report job failed: {exc}")
