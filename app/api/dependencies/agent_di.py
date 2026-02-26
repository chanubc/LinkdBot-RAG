from fastapi import Depends

from app.api.dependencies.auth_di import get_telegram_client
from app.api.dependencies.link_di import get_link_repository
from app.api.dependencies.rag_di import get_reranker, get_retriever
from app.application.agents.knowledge_agent import KnowledgeAgent
from app.domain.repositories.i_llm_gateway import ILLMGateway
from app.domain.repositories.i_router_llm import IRouterLLM
from app.domain.repositories.i_telegram_repository import ITelegramRepository
from app.infrastructure.llm.openai_llm_gateway import OpenAILLMGateway
from app.infrastructure.llm.router_llm import RouterLLMImpl
from app.infrastructure.repository.link_repository import LinkRepository
from app.rag.reranker import SimpleReranker
from app.rag.retriever import HybridRetriever


def get_llm_gateway() -> ILLMGateway:
    return OpenAILLMGateway()


def get_knowledge_agent(
    retriever: HybridRetriever = Depends(get_retriever),
    reranker: SimpleReranker = Depends(get_reranker),
    link_repo: LinkRepository = Depends(get_link_repository),
    telegram: ITelegramRepository = Depends(get_telegram_client),
    llm: ILLMGateway = Depends(get_llm_gateway),
) -> KnowledgeAgent:
    return KnowledgeAgent(retriever, reranker, link_repo, telegram, llm)


def get_router_llm() -> IRouterLLM:
    return RouterLLMImpl()
