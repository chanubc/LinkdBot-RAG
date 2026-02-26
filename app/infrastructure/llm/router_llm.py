import logging

from openai import AsyncOpenAI

from app.config import settings
from app.domain.entities.intent import Intent
from app.domain.repositories.i_router_llm import IRouterLLM, RouterOutput

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
사용자가 저장한 링크/메모 지식 베이스 봇의 메시지 분류기입니다.
사용자의 메시지를 분석하여 아래 intent 중 하나를 반환하세요.

- search: 저장된 링크/메모에서 특정 내용을 찾으려는 의도 (예: "머신러닝 자료 찾아줘", "파이썬 관련 내용 검색")
- memo: 내용을 메모/기록하려는 의도 (예: "오늘 배운 거 메모해줘", "이거 기록해둬")
- ask: 저장된 지식 기반으로 질문하거나 설명을 요청하는 의도 (예: "RAG가 뭐야?", "안 읽은 링크 보여줘", "이게 무슨 내용이야?")
- start: 봇 시작 또는 Notion 연동 의도 (예: "시작", "노션 연동하고 싶어")
- help: 사용법/도움말 요청 (예: "어떻게 써?", "도움말", "사용법 알려줘")
- unknown: 봇과 무관한 메시지 (예: "안녕", "오늘 날씨", "뭐해")

query는 실제 처리에 사용할 핵심 텍스트를 추출하세요.
- search: 검색어
- memo: 메모할 내용
- ask: 질문 텍스트
- start/help/unknown: null\
"""


class RouterLLMImpl(IRouterLLM):
    """GPT-4.1-mini + Structured Output 기반 메시지 의도 분류기."""

    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def route(self, text: str) -> RouterOutput:
        try:
            response = await self._openai.beta.chat.completions.parse(
                model="gpt-4.1-mini",
                messages=[
                    {"role": "system", "content": _SYSTEM_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format=RouterOutput,
            )
            result = response.choices[0].message.parsed
            if result is None:
                return RouterOutput(intent=Intent.UNKNOWN)
            logger.debug("RouterLLM: '%s' → intent=%s, query=%s", text, result.intent, result.query)
            return result
        except Exception:
            logger.exception("RouterLLM.route 오류, fallback to ASK")
            return RouterOutput(intent=Intent.ASK, query=text)
