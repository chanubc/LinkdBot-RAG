from typing import Protocol


class StateStorePort(Protocol):
    """OAuth state 저장/검증 Port."""

    def create(self, telegram_id: int) -> str:
        """state token 생성."""
        ...

    def consume(self, token: str) -> int | None:
        """state token 소비 (검증 후 삭제)."""
        ...
