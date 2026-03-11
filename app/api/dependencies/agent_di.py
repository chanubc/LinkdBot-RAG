from fastapi import Depends

from app.api.dependencies.link_di import get_link_repository
from app.api.dependencies.rag_di import get_reranker, get_retriever
from app.application.agents.knowledge_agent import KnowledgeAgent
from app.application.ports.chat_completion_port import ChatCompletionPort
from app.application.ports.intent_router_port import IntentRouterPort
from app.application.ports.knowledge_agent_port import KnowledgeAgentPort
from app.infrastructure.adapters.openai_intent_classifier import OpenAIIntentClassifier
from app.infrastructure.llm.openai_llm_gateway import OpenAILLMGateway
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.rag.reranker import SimpleReranker
from app.infrastructure.rag.retriever import HybridRetriever


def get_llm_gateway() -> ChatCompletionPort:
    return OpenAILLMGateway()


def get_intent_classifier(
    llm: ChatCompletionPort = Depends(get_llm_gateway),
) -> IntentRouterPort:
    """Port 반환: IntentRouterPort 구현체는 OpenAI."""
    return OpenAIIntentClassifier(llm)


def get_knowledge_agent(
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: SimpleReranker = Depends(get_reranker),
    link_repo: LinkRepository = Depends(get_link_repository),
    llm: ChatCompletionPort = Depends(get_llm_gateway),
) -> KnowledgeAgentPort:
    return KnowledgeAgent(retriever, reranker, link_repo, llm)
