from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    title: str
    url: str | None = None
    link_id: int | None = None


@dataclass(frozen=True, slots=True)
class KnowledgeAnswer:
    answer: str
    sources: list[KnowledgeSource] = field(default_factory=list)


class KnowledgeAgentPort(ABC):
    """Port: knowledge-answer generation."""

    @abstractmethod
    async def answer(self, telegram_id: int, query: str) -> KnowledgeAnswer:
        """Generate an answer and supporting sources for a user query."""
        pass
