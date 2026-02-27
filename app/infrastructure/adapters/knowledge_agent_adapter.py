from app.application.agents.knowledge_agent import KnowledgeAgent
from app.application.ports.agent_port import AgentPort
from app.application.ports.telegram_port import TelegramPort


class KnowledgeAgentAdapter(AgentPort):
    """Adapter: KnowledgeAgent를 AgentPort로 감싼다."""

    def __init__(
        self,
        knowledge_agent: KnowledgeAgent,
        telegram: TelegramPort,
    ):
        self._knowledge_agent = knowledge_agent
        self._telegram = telegram

    async def run(self, telegram_id: int, query: str) -> None:
        """AgentPort 구현: KnowledgeAgent 실행."""
        await self._telegram.send_message(telegram_id, "🤖 답변을 생성하는 중입니다...")
        await self._knowledge_agent.handle(telegram_id, query)
