from abc import ABC, abstractmethod

from app.application.models.llm import LLMChatCompletion, LLMMessage, LLMTool


class LLMGatewayPort(ABC):
    """Framework-independent LLM calling Port (Function Calling, chat, etc.)."""

    @abstractmethod
    async def chat_completions(
        self,
        messages: list[LLMMessage],
        model: str = "gpt-4o",
        tools: list[LLMTool] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
    ) -> LLMChatCompletion:
        """Send messages to LLM and receive response.

        Args:
            messages: List of LLMMessage objects
            model: Model identifier (provider-specific)
            tools: Function Calling tool definitions (optional)
            tool_choice: Tool selection mode (auto/required/none)
            temperature: Response diversity (sampling temperature)

        Returns:
            LLMChatCompletion: Domain model containing response and optional raw response
        """
        pass
