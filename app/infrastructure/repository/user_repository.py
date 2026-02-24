from cryptography.fernet import Fernet
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.domain.repositories.i_user_repository import IUserRepository
from app.models.user import User

_fernet = Fernet(settings.ENCRYPTION_KEY.encode())


class UserRepository(IUserRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def ensure_exists(self, telegram_id: int) -> User:
        """유저가 없으면 생성."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            user = User(telegram_id=telegram_id)
            self._db.add(user)
            await self._db.flush()
            await self._db.refresh(user)
        return user

    async def upsert_notion_credentials(
        self,
        telegram_id: int,
        notion_access_token: str,
        notion_database_id: str | None,
    ) -> User:
        """Notion 인증 정보 저장 (토큰 암호화). commit은 Service에서 호출."""
        encrypted = _fernet.encrypt(notion_access_token.encode()).decode()
        user = await self.get_by_telegram_id(telegram_id)
        if user:
            user.notion_access_token = encrypted
            user.notion_database_id = notion_database_id
        else:
            user = User(
                telegram_id=telegram_id,
                notion_access_token=encrypted,
                notion_database_id=notion_database_id,
            )
            self._db.add(user)
        await self._db.flush()
        return user

    async def get_decrypted_token(self, telegram_id: int) -> str | None:
        """복호화된 Notion access token 반환."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user or not user.notion_access_token:
            return None
        return _fernet.decrypt(user.notion_access_token.encode()).decode()
