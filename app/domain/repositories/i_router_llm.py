from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.domain.entities.intent import Intent


class RouterOutput(BaseModel):
    intent: Intent
    query: str | None = None  # search/ask용 핵심 텍스트, memo용 내용


class IRouterLLM(ABC):
    """메시지 의도 분류 인터페이스."""

    @abstractmethod
    async def route(self, text: str) -> RouterOutput:
        """사용자 메시지 → RouterOutput(intent, query)."""
        pass
