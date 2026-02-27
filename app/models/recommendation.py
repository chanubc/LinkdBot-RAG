from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer
from sqlalchemy.sql import func

from app.infrastructure.database import Base


class Recommendation(Base):
    __tablename__ = "recommendations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    link_id = Column(
        Integer,
        ForeignKey("links.id", ondelete="CASCADE"),
        nullable=False,
    )
    user_id = Column(
        BigInteger,
        ForeignKey("users.telegram_id", ondelete="CASCADE"),
        nullable=False,
    )
    recommended_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
