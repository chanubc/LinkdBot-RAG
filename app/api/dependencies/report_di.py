"""주간 리포트 UseCase 의존성 주입."""
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies.auth_di import get_telegram_client, get_user_repository
from app.api.dependencies.link_di import get_openai_client
from app.application.ports.openai_llm_port import OpenAILLMPort
from app.application.ports.telegram_port import TelegramPort
from app.application.usecases.generate_weekly_report_usecase import GenerateWeeklyReportUseCase
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_recommendation_repository import IRecommendationRepository
from app.domain.repositories.i_user_repository import IUserRepository
from app.infrastructure.database import get_db
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.repository.recommendation_repository import RecommendationRepository
from app.infrastructure.repository.user_repository import UserRepository


def get_recommendation_repository(
    db: AsyncSession = Depends(get_db),
) -> IRecommendationRepository:
    return RecommendationRepository(db)


def get_weekly_report_usecase(
    db: AsyncSession = Depends(get_db),
    user_repo: IUserRepository = Depends(get_user_repository),
    link_repo: ILinkRepository = Depends(
        lambda db=Depends(get_db): LinkRepository(db)
    ),
    rec_repo: IRecommendationRepository = Depends(get_recommendation_repository),
    openai: OpenAILLMPort = Depends(get_openai_client),
    telegram: TelegramPort = Depends(get_telegram_client),
) -> GenerateWeeklyReportUseCase:
    return GenerateWeeklyReportUseCase(db, user_repo, link_repo, rec_repo, openai, telegram)


def build_weekly_report_usecase(session: AsyncSession) -> GenerateWeeklyReportUseCase:
    """스케줄러에서 직접 호출 (FastAPI Depends 없이) 사용하는 팩토리."""
    from app.infrastructure.external.telegram_client import TelegramRepository
    from app.infrastructure.llm.openai_client import OpenAIRepository

    return GenerateWeeklyReportUseCase(
        db=session,
        user_repo=UserRepository(session),
        link_repo=LinkRepository(session),
        rec_repo=RecommendationRepository(session),
        openai=OpenAIRepository(),
        telegram=TelegramRepository(),
    )
