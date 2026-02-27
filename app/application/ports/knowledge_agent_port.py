from abc import ABC, abstractmethod


class KnowledgeAgentPort(ABC):
    """Port: knowledge processing execution (search, answer, tool dispatch)."""

    @abstractmethod
    async def run(self, telegram_id: int, query: str) -> None:
        """Run the agent for a user query and send response via Telegram.

        Args:
            telegram_id: User's Telegram ID
            query: User question/query
        """
        pass
