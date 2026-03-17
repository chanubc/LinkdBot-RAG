from openai import AsyncOpenAI
from pydantic import BaseModel

from app.core.config import settings
from app.application.models.llm import LLMChatCompletion, LLMMessage, LLMTool
from app.application.ports.chat_completion_port import ChatCompletionPort


class OpenAILLMGateway(ChatCompletionPort):
    """OpenAI API adapter for ChatCompletionPort."""

    def __init__(self) -> None:
        self._client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def chat_completions(
        self,
        messages: list[LLMMessage],
        model: str = "gpt-4.1",
        tools: list[LLMTool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        response_format: type[BaseModel] | None = None,
    ) -> LLMChatCompletion:
        """Call OpenAI chat.completions API and convert response to domain model."""
        openai_messages = [self._message_to_openai(msg) for msg in messages]

        # Structured Output path
        if response_format is not None:
            if tools:
                raise ValueError("Structured output does not support tools.")
            response = await self._client.beta.chat.completions.parse(
                model=model,
                messages=openai_messages,
                response_format=response_format,
                temperature=temperature,
            )
            choice = response.choices[0]
            response_message = LLMMessage(
                role=choice.message.role,
                content=choice.message.content,
            )
            return LLMChatCompletion(
                message=response_message,
                parsed=choice.message.parsed,
                raw=response,
            )

        # Standard chat completion path
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
