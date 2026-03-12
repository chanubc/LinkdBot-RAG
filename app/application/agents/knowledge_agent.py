import json

from app.domain.repositories.i_link_repository import ILinkRepository
from app.application.models.llm import LLMMessage
from app.application.ports.chat_completion_port import ChatCompletionPort
from app.application.ports.knowledge_agent_port import (
    KnowledgeAgentPort,
    KnowledgeAnswer,
    KnowledgeSource,
)
from app.infrastructure.rag.reranker import SimpleReranker
from app.infrastructure.rag.retriever import HybridRetriever
from app.core.llm_models import LLM_AGENT
from app.core.prompts.knowledge_agent import KNOWLEDGE_AGENT_PROMPT, TOOLS

from app.core.logger import logger


class KnowledgeAgent(KnowledgeAgentPort):
    """OpenAI Function Calling 기반 AI Agent."""

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: SimpleReranker,
        link_repo: ILinkRepository,
        llm: ChatCompletionPort,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._link_repo = link_repo
        self._llm = llm

    async def answer(self, telegram_id: int, query: str) -> KnowledgeAnswer:
        """Function Calling loop: intent → tool → synthesis → answer text + sources."""
        collected_sources: list[KnowledgeSource] = []
        try:
            messages: list[LLMMessage] = [
                LLMMessage(role="system", content=KNOWLEDGE_AGENT_PROMPT),
                LLMMessage(role="user", content=query),
            ]

            response = await self._llm.chat_completions(
                messages=messages,
                model=LLM_AGENT,
                tools=TOOLS,
                tool_choice="required",
            )

            if not response.tool_calls:
                logger.warning(
                    "tool_choice=required but no tool_calls returned (telegram_id=%d)", telegram_id
                )
                return KnowledgeAnswer(answer="답변을 생성할 수 없습니다.")

            messages.append(response.message)

            for tool_call in response.tool_calls:
                tool_result = await self._execute_tool(
                    telegram_id,
                    tool_call["function"]["name"],
                    json.loads(tool_call["function"]["arguments"]),
                )
                collected_sources.extend(self._extract_sources(tool_result))
                messages.append(
                    LLMMessage(
                        role="tool",
                        content=json.dumps(tool_result, ensure_ascii=False),
                        tool_call_id=tool_call["id"],
                    )
                )

            final_response = await self._llm.chat_completions(
                messages=messages,
                model=LLM_AGENT,
            )
            return KnowledgeAnswer(
                answer=final_response.message.content or "답변을 생성할 수 없습니다.",
                sources=self._dedupe_sources(collected_sources),
            )

        except Exception:
            logger.exception(f"KnowledgeAgent.answer error (telegram_id={telegram_id})")
            return KnowledgeAnswer(answer="❌ 처리 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.")

    async def _execute_tool(
        self, telegram_id: int, tool_name: str, args: dict
    ) -> list | str:
        """Tool 이름에 따라 함수 디스패치."""
        if tool_name == "search_knowledge_base":
            query = args["query"]
            raw = await self._retriever.retrieve(telegram_id, query, top_k=10)
            results = self._reranker.rerank(raw, top_k=5)
            return [
                {
                    "title": r.get("title"),
                    "url": r.get("url"),
                    "link_id": r.get("link_id"),
                    "chunk": r.get("chunk_content"),
                    "similarity": round(r.get("similarity", 0), 3),
                }
                for r in results
            ]
        elif tool_name == "get_unread_links":
            limit = args.get("limit", 5)
            links = await self._link_repo.get_unread_links(telegram_id, limit)
            return [
                {
                    "title": link.title,
                    "url": link.url,
                    "link_id": link.id,
                    "category": link.category,
                    "summary": link.summary,
                }
                for link in links
            ]
        return f"알 수 없는 도구: {tool_name}"

    @staticmethod
    def _extract_sources(tool_result: list | str) -> list[KnowledgeSource]:
        if not isinstance(tool_result, list):
            return []

        sources: list[KnowledgeSource] = []
        for item in tool_result:
            if not isinstance(item, dict):
                continue
            title = (item.get("title") or "").strip()
            url = item.get("url")
            if not title and not url:
                continue
            link_id = item.get("link_id")
            sources.append(KnowledgeSource(title=title or "제목 없음", url=url, link_id=link_id))
        return sources

    @staticmethod
    def _dedupe_sources(sources: list[KnowledgeSource]) -> list[KnowledgeSource]:
        deduped: list[KnowledgeSource] = []
        seen: set[tuple[int | None, str | None, str]] = set()
        for source in sources:
            key = (source.link_id, source.url, source.title)
            if key in seen:
                continue
            seen.add(key)
            deduped.append(source)
        return deduped[:5]
