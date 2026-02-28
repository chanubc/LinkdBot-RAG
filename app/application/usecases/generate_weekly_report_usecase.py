"""주간 리포트 생성 UseCase.

Flow:
1. 관심사 Drift 계산 (최근 7일 vs 과거 30일 카테고리 비중)
2. Interest Centroid 계산 (최근 7일 임베딩, 없으면 전체 폴백)
3. 최근 14일 추천 이력 제외하고 재활성화 후보 조회
4. Reactivation Score 기반 최적 링크 1개 선정
5. LLM_ANALYSIS(gpt-4.1-mini)로 브리핑 생성
6. Telegram 푸시 (읽음 처리 버튼 포함)
7. 추천 이력 기록 + DB 커밋
"""
import html
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.application.ports.ai_analysis_port import AIAnalysisPort
from app.application.ports.telegram_port import TelegramPort
from app.domain.drift import calculate_drift
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_recommendation_repository import IRecommendationRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.scoring import compute_interest_centroid, select_reactivation_link

logger = logging.getLogger(__name__)


class GenerateWeeklyReportUseCase:
    def __init__(
        self,
        db: AsyncSession,
        user_repo: IUserRepository,
        link_repo: ILinkRepository,
        rec_repo: IRecommendationRepository,
        openai: AIAnalysisPort,
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
                await self._db.rollback()
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

        # 1. Drift 계산 (current: 최근 7일, past: 7일~30일 — 겹침 없이 분리)
        current_cats = await self._link_repo.get_categories_by_period(user_id, week_ago, now)
        past_cats = await self._link_repo.get_categories_by_period(user_id, month_ago, week_ago)
        if len(current_cats) >= 3:
            tvd, delta = calculate_drift(current_cats, past_cats)
        else:
            tvd, delta = 0.0, {}

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
            _build_briefing_prompt(best, tvd, delta, current_cats)
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


def _build_briefing_prompt(
    best: dict,
    tvd: float,
    delta: dict[str, float],
    current_cats: list[str],
) -> str:
    if tvd > 0.1:
        top_gains = sorted(
            [(c, d) for c, d in delta.items() if d > 0],
            key=lambda t: t[1],
            reverse=True,
        )[:2]
        top_losses = sorted(
            [(c, d) for c, d in delta.items() if d < 0],
            key=lambda t: t[1],
        )[:2]
        drift_lines = []
        for c, d in top_gains:
            drift_lines.append(f"  ▲ {c} (+{d:.0%})")
        for c, d in top_losses:
            drift_lines.append(f"  ▼ {c} ({d:.0%})")
        drift_summary = "Interest drift:\n" + "\n".join(drift_lines)
    else:
        drift_summary = "Interest drift: stable (no significant change)"

    categories_str = ", ".join(current_cats[:10]) if current_cats else "none"

    return f"""\
Generate a weekly knowledge report for the user.

[This week's interest categories]: {categories_str}
[{drift_summary}]

[Link to revisit]
Title: {best.get('title', 'No title')}
Summary: {best.get('summary', '')}
Category: {best.get('category', '')}

Based on the above information:
1. Summarize this week's interest trends in one sentence
2. Explain why the recommended link is useful right now (2-3 sentences)
3. Provide an encouraging closing remark

Write in Korean, in a friendly and concise tone. Total 5-7 sentences."""


def _build_report_message(briefing: str, best: dict) -> str:
    title = html.escape(best.get("title", "제목 없음"))
    url = best.get("url", "")
    url_line = f'\n🔗 <a href="{html.escape(url)}">{html.escape(url)}</a>' if url else ""
    return (
        f"📊 <b>이번 주 지식 리포트</b>\n\n"
        f"{html.escape(briefing)}\n\n"
        f"━━━━━━━━━━━━━━━\n"
        f"📌 <b>다시 보기 추천</b>\n"
        f"<b>{title}</b>{url_line}"
    )
