from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.application.models.llm import LLMChatCompletion, LLMMessage, LLMTool


class ChatCompletionPort(ABC):
    """Framework-independent LLM chat completion Port (Function Calling, chat, etc.)."""

    @abstractmethod
    async def chat_completions(
        self,
        messages: list[LLMMessage],
        model: str = "gpt-4.1",
        tools: list[LLMTool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
        response_format: type[BaseModel] | None = None,
    ) -> LLMChatCompletion:
        """Send messages to LLM and receive response.

        Args:
            messages: List of LLMMessage objects
            model: Model identifier (provider-specific)
            tools: Function Calling tool definitions (optional)
            tool_choice: Tool selection mode (auto/required/none)
            temperature: Response diversity (sampling temperature)
            response_format: Pydantic model for Structured Output (optional)

        Returns:
            LLMChatCompletion: Domain model containing response and optional raw response
        """
        pass
