from app.application.models.llm import LLMMessage
from app.application.ports.chat_completion_port import ChatCompletionPort
from app.application.ports.intent_router_port import IntentRouterPort, RouterOutput
from app.core.llm_models import LLM_ROUTER
from app.core.prompts.intent_classifier import INTENT_CLASSIFIER_PROMPT
from app.domain.entities.intent import Intent

from app.core.logger import logger


class OpenAIIntentClassifier(IntentRouterPort):
    """Adapter: OpenAI gpt-4.1-mini + Structured Output으로 Intent 라우팅."""

    def __init__(self, llm: ChatCompletionPort) -> None:
        self._llm = llm

    async def classify(self, text: str) -> RouterOutput:
        """IntentRouterPort 구현: OpenAI로 Intent 분류."""
        try:
            response = await self._llm.chat_completions(
                messages=[
                    LLMMessage(role="system", content=INTENT_CLASSIFIER_PROMPT),
                    LLMMessage(role="user", content=text),
                ],
                model=LLM_ROUTER,
                response_format=RouterOutput,
            )
            result = response.parsed
            if result is None:
                return RouterOutput(intent=Intent.UNKNOWN)
            logger.debug(f"Classified: '{text}' → intent={result.intent}, query={result.query}")
            return result
        except Exception:
            logger.exception("Intent classification failed, fallback to ASK")
            return RouterOutput(intent=Intent.ASK, query=text)
