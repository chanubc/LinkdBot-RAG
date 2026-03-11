from abc import ABC, abstractmethod


class KnowledgeAgentPort(ABC):
    """Port: knowledge-answer generation."""

    @abstractmethod
    async def answer(self, telegram_id: int, query: str) -> str:
        """Generate an answer for a user query.

        Args:
            telegram_id: User's Telegram ID
            query: User question/query
        """
        pass
