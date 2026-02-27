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

from app.application.ports.openai_llm_port import OpenAILLMPort
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
        openai: OpenAILLMPort,
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
    drift_summary = ""
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
        drift_summary = "관심사 변화:\n" + "\n".join(drift_lines)
    else:
        drift_summary = "관심사 변화: 안정적 (큰 변화 없음)"

    categories_str = ", ".join(current_cats[:10]) if current_cats else "없음"

    return f"""사용자의 주간 지식 리포트를 생성해주세요.

[이번 주 관심 카테고리]: {categories_str}
[{drift_summary}]

[다시 볼 링크]
제목: {best.get('title', '제목 없음')}
요약: {best.get('summary', '')}
카테고리: {best.get('category', '')}

위 정보를 바탕으로:
1. 이번 주 관심사 흐름을 한 문장으로 요약
2. 다시 볼 링크가 왜 지금 유용한지 설명 (2~3문장)
3. 마무리 응원 한 마디

친근하고 간결하게 한국어로 작성해주세요. 총 5~7문장."""


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
