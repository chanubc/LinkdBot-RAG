"""Framework-agnostic LLM models."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMMessage:
    """Framework-independent LLM message model."""

    role: str
    """Message role (e.g., 'system', 'user', 'assistant', 'tool')."""

    content: Any
    """Message content. Can be string or provider-specific structure."""

    name: str | None = None
    """Optional: Function name or message sender identifier."""

    tool_call_id: str | None = None
    """Optional: Tool call ID for tool responses."""

    tool_calls: list[dict] | None = None
    """Optional: Tool calls made by the assistant (Function Calling)."""

    metadata: dict[str, Any] = field(default_factory=dict)
    """Optional: Provider-specific extended metadata."""


@dataclass
class LLMTool:
    """Framework-independent Function Calling tool definition."""

    name: str
    """Tool name."""

    description: str | None = None
    """Tool description."""

    parameters: dict[str, Any] | None = None
    """Tool parameters (JSON schema format)."""


@dataclass
class LLMChatCompletion:
    """LLM chat completion response domain model."""

    message: LLMMessage
    """Primary response message (typically assistant role)."""

    tool_calls: list[dict] | None = None
    """Optional: Tool calls from the response (for Function Calling)."""

    raw: Any | None = None
    """Optional: Provider's native response object for debugging."""
