import json
import logging

from app.domain.repositories.i_link_repository import ILinkRepository
from app.domain.repositories.i_llm_gateway import ILLMGateway
from app.domain.repositories.i_telegram_repository import ITelegramRepository
from app.rag.reranker import SimpleReranker
from app.rag.retriever import HybridRetriever

logger = logging.getLogger(__name__)

_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_knowledge_base",
            "description": "사용자가 저장한 링크와 메모에서 관련 내용을 검색합니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "검색할 질문 또는 키워드",
                    }
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unread_links",
            "description": "사용자가 아직 읽지 않은 저장된 링크 목록을 가져옵니다.",
            "parameters": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "가져올 링크 수 (기본값: 5)",
                    }
                },
                "required": [],
            },
        },
    },
]


class KnowledgeAgent:
    """OpenAI Function Calling 기반 AI Agent."""

    def __init__(
        self,
        retriever: HybridRetriever,
        reranker: SimpleReranker,
        link_repo: ILinkRepository,
        telegram: ITelegramRepository,
        llm: ILLMGateway,
    ) -> None:
        self._retriever = retriever
        self._reranker = reranker
        self._link_repo = link_repo
        self._telegram = telegram
        self._llm = llm

    async def handle(self, telegram_id: int, query: str) -> None:
        """Function Calling 루프: intent → tool → synthesis → send."""
        try:
            messages: list[dict] = [
                {
                    "role": "system",
                    "content": (
                        "당신은 사용자의 개인 지식 베이스 도우미입니다. "
                        "사용자가 저장한 링크와 메모를 기반으로 질문에 답하세요. "
                        "도구를 활용하여 관련 정보를 검색하고 정확하고 유용한 답변을 제공하세요."
                    ),
                },
                {"role": "user", "content": query},
            ]

            msg = await self._llm.chat_completions(
                messages=messages,
                model="gpt-4o",
                tools=_TOOLS,
                tool_choice="auto",
            )

            tool_calls = msg.get("tool_calls")
            if not tool_calls:
                await self._telegram.send_message(
                    telegram_id, msg.get("content") or "답변을 생성할 수 없습니다."
                )
                return

            messages.append(msg)
            for tool_call in tool_calls:
                tool_result = await self._execute_tool(
                    telegram_id,
                    tool_call["function"]["name"],
                    json.loads(tool_call["function"]["arguments"]),
                )
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": json.dumps(tool_result, ensure_ascii=False),
                })

            final_response = await self._llm.chat_completions(
                messages=messages,
                model="gpt-4o",
            )
            answer = final_response.get("content") or "답변을 생성할 수 없습니다."
            await self._telegram.send_message(telegram_id, answer)

        except Exception as exc:
            logger.exception("AgentService.handle 오류 (telegram_id=%s)", telegram_id)
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
