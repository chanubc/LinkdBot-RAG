"""Port → Adapter 매핑 (Infrastructure 구현체 생성)."""

from fastapi import Depends

from app.application.ports.knowledge_agent_port import KnowledgeAgentPort
from app.application.ports.intent_router_port import IntentRouterPort
from app.application.ports.telegram_port import TelegramPort
from app.infrastructure.adapters.knowledge_agent_adapter import KnowledgeAgentAdapter
from app.infrastructure.adapters.openai_intent_classifier import OpenAIIntentClassifier
from app.application.agents.knowledge_agent import KnowledgeAgent
from app.api.dependencies.auth_di import get_telegram_client
from app.api.dependencies.agent_di import get_knowledge_agent


def get_intent_classifier() -> IntentRouterPort:
    """Port 반환: IntentRouterPort 구현체는 OpenAI."""
    return OpenAIIntentClassifier()


def get_agent(
    knowledge_agent: KnowledgeAgent = Depends(get_knowledge_agent),
    telegram: TelegramPort = Depends(get_telegram_client),
) -> KnowledgeAgentPort:
    """Port 반환: KnowledgeAgentPort 구현체는 KnowledgeAgentAdapter."""
    return KnowledgeAgentAdapter(knowledge_agent, telegram)
