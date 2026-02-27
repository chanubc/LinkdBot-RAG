from fastapi import Depends

from app.api.dependencies.auth_di import get_telegram_client
from app.api.dependencies.link_di import get_link_repository
from app.api.dependencies.rag_di import get_reranker, get_retriever
from app.application.agents.knowledge_agent import KnowledgeAgent
from app.application.ports.telegram_port import TelegramPort
from app.application.ports.llm_gateway_port import LLMGatewayPort
from app.infrastructure.llm.openai_llm_gateway import OpenAILLMGateway
from app.infrastructure.repository.link_repository import LinkRepository
from app.infrastructure.rag.reranker import SimpleReranker
from app.infrastructure.rag.retriever import HybridRetriever


def get_llm_gateway() -> LLMGatewayPort:
    return OpenAILLMGateway()


def get_knowledge_agent(
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: SimpleReranker = Depends(get_reranker),
    link_repo: LinkRepository = Depends(get_link_repository),
    telegram: TelegramPort = Depends(get_telegram_client),
    llm: LLMGatewayPort = Depends(get_llm_gateway),
) -> KnowledgeAgent:
    return KnowledgeAgent(retriever, reranker, link_repo, telegram, llm)
