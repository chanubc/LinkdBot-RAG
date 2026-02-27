from abc import ABC, abstractmethod

from pydantic import BaseModel

from app.domain.entities.intent import Intent


class ClassifierOutput(BaseModel):
    """Intent 분류 결과."""

    intent: Intent
    query: str | None = None


class IntentClassifierPort(ABC):
    """
    Port: 일반 텍스트를 Intent로 분류하는 외부 시스템과의 계약.

    Application은 OpenAI/Anthropic/etc의 구현체를 모르고,
    이 Interface만을 통해 의존한다.
    """

    @abstractmethod
    async def classify(self, text: str) -> ClassifierOutput:
        """사용자 텍스트를 Intent로 분류하고 핵심 쿼리를 추출한다.

        Args:
            text: 사용자 입력 텍스트

        Returns:
            ClassifierOutput: intent와 query
        """
        pass
