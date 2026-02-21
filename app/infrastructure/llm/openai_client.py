import json

from openai import AsyncOpenAI

from app.config import settings


class OpenAIClient:
    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def analyze_content(self, content: str) -> dict:
        """GPT-4o로 제목 / 요약 / 카테고리 / 키워드 추출."""
        prompt = f"""다음 웹 콘텐츠를 분석하여 JSON으로 반환하세요.

콘텐츠:
{content[:8000]}

반환 형식:
{{
  "title": "콘텐츠 제목 (한 줄, 50자 이내)",
  "summary": "핵심 내용 3줄 요약",
  "category": "AI | Dev | Career | Business | Science | Other 중 하나",
  "keywords": ["키워드1", "키워드2", "키워드3", "키워드4", "키워드5"]
}}

JSON만 반환하세요."""

        response = await self._client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    async def embed(self, texts: list[str]) -> list[list[float]]:
        """text-embedding-3-small으로 벡터 임베딩 생성."""
        response = await self._client.embeddings.create(
            model="text-embedding-3-small",
            input=texts,
        )
        return [item.embedding for item in response.data]
