import logging

from openai import AsyncOpenAI

from app.application.ports.intent_classifier_port import (
    ClassifierOutput,
    IntentClassifierPort,
)
from app.core.config import settings
from app.domain.entities.intent import Intent
from app.prompts.intent_classifier import INTENT_CLASSIFIER_PROMPT

logger = logging.getLogger(__name__)


class OpenAIIntentClassifier(IntentClassifierPort):
    """Adapter: OpenAI gpt-4o-mini + Structured Output으로 Intent 분류."""

    def __init__(self) -> None:
        self._openai = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def classify(self, text: str) -> ClassifierOutput:
        """IntentClassifierPort 구현: OpenAI로 Intent 분류."""
        try:
            response = await self._openai.beta.chat.completions.parse(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": INTENT_CLASSIFIER_PROMPT},
                    {"role": "user", "content": text},
                ],
                response_format=ClassifierOutput,
            )
            result = response.choices[0].message.parsed
            if result is None:
                return ClassifierOutput(intent=Intent.UNKNOWN)
            logger.debug("Classified: '%s' → intent=%s, query=%s", text, result.intent, result.query)
            return result
        except Exception:
            logger.exception("Intent classification failed, fallback to ASK")
            return ClassifierOutput(intent=Intent.ASK, query=text)
