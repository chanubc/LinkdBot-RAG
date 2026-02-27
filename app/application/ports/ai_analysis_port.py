from abc import ABC, abstractmethod

from app.domain.entities.content_analysis import ContentAnalysis


class AIAnalysisPort(ABC):
    """AI task execution Port (content analysis, embedding, text generation)."""

    @abstractmethod
    async def analyze_content(self, content: str) -> ContentAnalysis:
        """Extract title / summary / category / keywords from content."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings with text-embedding-3-small."""
        pass

    @abstractmethod
    async def generate_briefing(self, prompt: str) -> str:
        """Generate weekly briefing text."""
        pass
