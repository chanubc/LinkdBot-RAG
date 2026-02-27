from abc import ABC, abstractmethod


class OpenAILLMPort(ABC):
    """OpenAI API 통신 Port."""

    @abstractmethod
    async def analyze_content(self, content: str) -> dict:
        """GPT-4o로 제목 / 요약 / 카테고리 / 키워드 추출."""
        pass

    @abstractmethod
    async def embed(self, texts: list[str]) -> list[list[float]]:
        """text-embedding-3-small으로 벡터 임베딩 생성."""
        pass
