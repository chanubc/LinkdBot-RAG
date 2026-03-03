import json

from app.domain.repositories.i_link_repository import ILinkRepository
from app.application.models.llm import LLMMessage
from app.application.ports.telegram_port import TelegramPort
from app.application.ports.chat_completion_port import ChatCompletionPort
from app.infrastructure.rag.reranker import SimpleReranker
from app.infrastructure.rag.retriever import HybridRetriever
from app.core.llm_models import LLM_AGENT
from app.core.prompts.knowledge_agent import KNOWLEDGE_AGENT_PROMPT, TOOLS

from app.core.logger import logger


class KnowledgeAgent:
    """OpenAI Function Calling 기반 AI Agent."""

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: SimpleReranker,
        link_repo: ILinkRepository,
        telegram: TelegramPort,
        llm: ChatCompletionPort,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._link_repo = link_repo
        self._telegram = telegram
        self._llm = llm

    async def handle(self, telegram_id: int, query: str) -> None:
        """Function Calling loop: intent → tool → synthesis → send."""
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
                logger.warning(f"tool_choice=required but no tool_calls returned (telegram_id={telegram_id})")
                await self._telegram.send_message(telegram_id, "답변을 생성할 수 없습니다.")
                return

            # Add assistant response to messages
            messages.append(response.message)

            # Execute tool calls
            for tool_call in response.tool_calls:
                tool_result = await self._execute_tool(
                    telegram_id,
                    tool_call["function"]["name"],
                    json.loads(tool_call["function"]["arguments"]),
                )
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
            answer = final_response.message.content or "답변을 생성할 수 없습니다."
            await self._telegram.send_message(telegram_id, answer)

        except Exception as exc:
            logger.exception(f"KnowledgeAgent.handle error (telegram_id={telegram_id})")
            await self._telegram.send_message(
                telegram_id, f"❌ 처리 실패: {str(exc)[:200]}"
            )

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
                    "category": link.category,
                    "summary": link.summary,
                }
                for link in links
            ]
        return f"알 수 없는 도구: {tool_name}"
