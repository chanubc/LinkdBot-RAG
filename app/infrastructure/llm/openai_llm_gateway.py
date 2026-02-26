import logging

from openai import AsyncOpenAI

from app.config import settings
from app.application.ports.llm_gateway_port import LLMGatewayPort

logger = logging.getLogger(__name__)


class OpenAILLMGateway(LLMGatewayPort):
    """OpenAI API를 통한 범용 LLM 호출 구현체."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat_completions(
        self,
        messages: list[dict],
        model: str = "gpt-4o",
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
    ) -> dict:
        """OpenAI chat.completions API 호출."""
        kwargs = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
        }
        if tools:
            kwargs["tools"] = tools
            kwargs["tool_choice"] = tool_choice

        response = await self._client.chat.completions.create(**kwargs)
        return response.choices[0].message.model_dump()
