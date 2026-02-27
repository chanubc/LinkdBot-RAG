from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.domain.entities.intent import Intent


class RouterOutput(BaseModel):
    """Intent routing result."""

    intent: Intent
    query: str | None = None


class IntentRouterPort(ABC):
    """Port: LLM-based branching decision (text → Intent routing)."""

    @abstractmethod
    async def classify(self, text: str) -> RouterOutput:
        """Classify user text into an Intent and extract the core query.

        Args:
            text: User input text

        Returns:
            RouterOutput: intent and optional query
        """
        pass
