from abc import ABC, abstractmethod


class StateStorePort(ABC):
    """
    Port: OAuth state 저장/검증을 위한 외부 시스템과의 계약.

    Application은 Redis/Memory/DB 기반 상태 저장소의 구현체를 모르고,
    이 Interface만을 통해 의존한다.
    """

    @abstractmethod
    def create(self, telegram_id: int) -> str:
        """state token 생성.

        Args:
            telegram_id: 사용자 Telegram ID

        Returns:
            str: 생성된 state token
        """
        pass

    @abstractmethod
    def consume(self, token: str) -> int | None:
        """state token 소비 (검증 후 삭제).

        Args:
            token: 검증할 state token

        Returns:
            int | None: 해당 telegram_id 또는 None (검증 실패)
        """
        pass
