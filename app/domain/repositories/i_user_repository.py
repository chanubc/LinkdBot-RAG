from abc import ABC, abstractmethod

from app.models.user import User


class IUserRepository(ABC):
    @abstractmethod
    async def get_by_telegram_id(self, telegram_id: int) -> User | None: ...

    @abstractmethod
    async def ensure_exists(self, telegram_id: int) -> User: ...

    @abstractmethod
    async def upsert_notion_credentials(
        self,
        telegram_id: int,
        notion_access_token: str,
        notion_database_id: str | None,
    ) -> User: ...

    @abstractmethod
    async def get_decrypted_token(self, telegram_id: int) -> str | None: ...

    @abstractmethod
    async def get_all_users(self) -> list[User]: ...
