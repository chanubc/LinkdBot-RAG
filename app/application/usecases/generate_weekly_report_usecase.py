"""주간 리포트 생성 UseCase.

Flow:
1. 관심사 Drift 계산 (최근 7일 vs 과거 30일 카테고리 비중)
2. Interest Centroid 계산 (최근 7일 임베딩, 없으면 전체 폴백)
3. 최근 14일 추천 이력 제외하고 재활성화 후보 조회
4. Reactivation Score 기반 최적 링크 1개 선정
5. GPT-4o-mini로 브리핑 생성
6. Telegram 푸시 (읽음 처리 버튼 포함)
7. 추천 이력 기록 + DB 커밋
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.ai_task_port import AITaskPort
from app.application.ports.telegram_port import TelegramPort
from app.domain.drift import calculate_drift
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_recommendation_repository import IRecommendationRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.scoring import compute_interest_centroid, select_reactivation_link
from app.prompts.weekly_briefing import build_briefing_prompt

logger = logging.getLogger(__name__)


class GenerateWeeklyReportUseCase:
    def __init__(
        self,
        db: AsyncSession,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        rec_repo: IRecommendationRepository,
        openai: AITaskPort,
        telegram: TelegramPort,
    ) -> None:
        self._db = db
        self._user_repo = user_repo
        self._link_repo = link_repo
        self._rec_repo = rec_repo
        self._openai = openai
        self._telegram = telegram

    async def execute_for_all_users(self) -> None:
        """전체 유저 대상 주간 리포트 실행 (스케줄러 진입점)."""
        users = await self._user_repo.get_all_users()
        for user in users:
            try:
                await self.execute(user.telegram_id)
            except Exception as exc:
                logger.error(
                    "Weekly report failed for user %s: %s",
                    user.telegram_id,
                    exc,
                    exc_info=True,
                )

    async def execute(self, user_id: int) -> None:
        """단일 유저 주간 리포트 생성 및 전송."""
        now = datetime.now(timezone.utc)
        week_ago = now - timedelta(days=7)
        month_ago = now - timedelta(days=30)

        # 1. Drift 계산
        current_cats = await self._link_repo.get_categories_by_period(user_id, week_ago, now)
        past_cats = await self._link_repo.get_categories_by_period(user_id, month_ago, now)
        tvd, delta = calculate_drift(current_cats, past_cats)

        # 2. Interest Centroid (최근 7일 → 전체 폴백)
        recent_embs = await self._link_repo.get_summary_embeddings_by_period(user_id, week_ago, now)
        if not recent_embs:
            recent_embs = await self._link_repo.get_all_summary_embeddings(user_id)
        centroid = compute_interest_centroid(recent_embs)

        if centroid is None:
            logger.info("User %s has no embeddings, skipping weekly report", user_id)
            return

        # 3. 최근 14일 추천 이력 제외
        excluded_ids = await self._rec_repo.get_recently_recommended_link_ids(user_id, within_days=14)

        # 4. 재활성화 후보 조회 + 최적 링크 선정
        candidates = await self._link_repo.get_reactivation_candidates(
            user_id, older_than_days=7, excluded_ids=excluded_ids
        )
        best = select_reactivation_link(candidates, centroid)

        if best is None:
            logger.info("User %s has no reactivation candidates, skipping", user_id)
            return

        # 5. LLM 브리핑 생성
        briefing = await self._openai.generate_briefing(
            build_briefing_prompt(best, tvd, delta, current_cats)
        )

        # 6. Telegram 전송 (읽음 처리 버튼 포함)
        message = _build_report_message(briefing, best)
        await self._telegram.send_weekly_report(
            chat_id=user_id,
            text=message,
            link_id=best["link_id"],
        )

        # 7. 추천 이력 기록 + 단일 커밋
        await self._rec_repo.record(link_id=best["link_id"], user_id=user_id)
        await self._db.commit()


def _build_report_message(briefing: str, best: dict) -> str:
    title = best.get("title", "제목 없음")
    url = best.get("url", "")
    url_line = f'\n🔗 <a href="{url}">{url}</a>' if url else ""
    return (
        f"📊 <b>이번 주 지식 리포트</b>\n\n"
        f"{briefing}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 <b>다시 보기 추천</b>\n"
        f"<b>{title}</b>{url_line}"
    )
