from abc import ABC, abstractmethod


class ILLMGateway(ABC):
    """범용 LLM 호출 인터페이스 (Function Calling, 일반 prompt 등)."""

    @abstractmethod
    async def chat_completions(
        self,
        messages: list[dict],
        model: str = "gpt-4o",
        tools: list[dict] | None = None,
        tool_choice: str = "auto",
        temperature: float = 0.7,
    ) -> dict:
        """LLM에 메시지를 보내고 응답을 받는다.

        Args:
            messages: OpenAI 형식의 메시지 리스트
            model: 사용할 모델명
            tools: Function Calling 도구 정의 (선택)
            tool_choice: 도구 선택 방식 (auto/required/none)
            temperature: 응답 다양성

        Returns:
            OpenAI 응답 객체의 choice[0].message dict 형태
        """
        pass
