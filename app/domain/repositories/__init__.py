# Domain Layer Repository Interfaces (Data Storage Contracts)

from app.domain.repositories.i_user_repository import IUserRepository
from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_chunk_repository import IChunkRepository
from app.domain.repositories.i_recommendation_repository import IRecommendationRepository

__all__ = [
    "IUserRepository",
    "ILinkRepository",
    "IChunkRepository",
    "IRecommendationRepository",
]
