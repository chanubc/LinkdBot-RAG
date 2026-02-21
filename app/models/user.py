from sqlalchemy import BigInteger, Column, String

from app.infrastructure.database import Base


class User(Base):
    __tablename__ = "users"

    telegram_id = Column(BigInteger, primary_key=True)
    notion_access_token = Column(String, nullable=True)  # Fernet 암호화
    notion_database_id = Column(String, nullable=True)
