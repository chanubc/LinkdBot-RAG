from openai import AsyncOpenAI

from app.core.config import settings
from app.application.ports.ai_task_port import AITaskPort
from app.domain.entities.content_analysis import ContentAnalysis
from app.prompts.analyze_content import ANALYZE_CONTENT_PROMPT


class OpenAIRepository(AITaskPort):
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def analyze_content(self, content: str) -> ContentAnalysis:
        """Extract title / summary / category / keywords from content."""
        response = await self._client.beta.chat.completions.parse(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": ANALYZE_CONTENT_PROMPT},
                {"role": "user", "content": content[:8000]},
            ],
            response_format=ContentAnalysis,
        )
        result = response.choices[0].message.parsed
        if result is None:
            raise ValueError("Content analysis returned no result")
        return result

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """text-embedding-3-small으로 벡터 임베딩 생성."""
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]

    async def generate_briefing(self, prompt: str) -> str:
        """주간 브리핑 텍스트 생성."""
        response = await self._client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.7,
        )
        return response.choices[0].message.content or ""
