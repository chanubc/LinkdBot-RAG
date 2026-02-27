import logging

from openai import AsyncOpenAI

from app.core.config import settings
from app.application.models.llm import LLMChatCompletion, LLMMessage, LLMTool
from app.application.ports.chat_completion_port import ChatCompletionPort

logger = logging.getLogger(__name__)


class OpenAILLMGateway(ChatCompletionPort):
    """OpenAI API adapter for ChatCompletionPort."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat_completions(
        self,
        messages: list[LLMMessage],
        model: str = "gpt-4o",
        tools: list[LLMTool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
    ) -> LLMChatCompletion:
        """Call OpenAI chat.completions API and convert response to domain model."""
        # Convert domain models to OpenAI format
        openai_messages = [self._message_to_openai(msg) for msg in messages]
        openai_tools = None
        if tools:
            openai_tools = [self._tool_to_openai(tool) for tool in tools]

        kwargs = {
            "model": model,
            "messages": openai_messages,
            "temperature": temperature,
        }
        if openai_tools:
            kwargs["tools"] = openai_tools
            kwargs["tool_choice"] = tool_choice

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]
        message = choice.message

        # Convert OpenAI response to domain model
        response_message = LLMMessage(
            role=message.role,
            content=message.content,
            name=getattr(message, "name", None),
        )

        tool_calls = None
        if hasattr(message, "tool_calls") and message.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "function": {
                        "name": tc.function.name,
                        "arguments": tc.function.arguments,
                    },
                }
                for tc in message.tool_calls
            ]

        response_message.tool_calls = tool_calls

        return LLMChatCompletion(
            message=response_message,
            tool_calls=tool_calls,
            raw=response,
        )

    @staticmethod
    def _message_to_openai(msg: LLMMessage) -> dict:
        """Convert LLMMessage to OpenAI format."""
        openai_msg: dict = {
            "role": msg.role,
            "content": msg.content,
        }
        if msg.name:
            openai_msg["name"] = msg.name
        if msg.tool_call_id:
            openai_msg["tool_call_id"] = msg.tool_call_id
        if msg.tool_calls:
            openai_msg["tool_calls"] = [
                {
                    "id": tc["id"],
                    "type": "function",
                    "function": tc["function"],
                }
                for tc in msg.tool_calls
            ]
        return openai_msg

    @staticmethod
    def _tool_to_openai(tool: LLMTool) -> dict:
        """Convert LLMTool to OpenAI format."""
        return {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters or {"type": "object", "properties": {}},
            },
        }
