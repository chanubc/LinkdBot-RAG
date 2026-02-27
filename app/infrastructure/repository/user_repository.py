from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import fernet as _fernet
from app.domain.repositories.i_user_repository import IUserRepository
from app.models.user import User


class UserRepository(IUserRepository):
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def get_by_telegram_id(self, telegram_id: int) -> User | None:
        result = await self._db.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        return result.scalar_one_or_none()

    async def ensure_exists(self, telegram_id: int, first_name: str | None = None) -> User:
        """유저가 없으면 생성, 기존 유저면 first_name 업데이트."""
        user = await self.get_by_telegram_id(telegram_id)
        if not user:
            user = User(telegram_id=telegram_id, first_name=first_name)
            self._db.add(user)
            await self._db.flush()
            await self._db.refresh(user)
        elif first_name and user.first_name != first_name:
            # 기존 유저도 first_name 업데이트 (profile 변경 대비)
            user.first_name = first_name
            await self._db.flush()
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
