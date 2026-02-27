from abc import ABC, abstractmethod


class AgentPort(ABC):
    """
    Port: AI Agent 실행을 위한 외부 시스템과의 계약.

    Application은 KnowledgeAgent/LangGraph/Custom Agent의 구현체를 모르고,
    이 Interface만을 통해 의존한다.
    """

    @abstractmethod
    async def run(self, telegram_id: int, query: str) -> None:
        """사용자 질문에 대해 에이전트를 실행하고 응답을 Telegram으로 전송한다.

        Args:
            telegram_id: 사용자 Telegram ID
            query: 사용자 질문/쿼리
        """
        pass
