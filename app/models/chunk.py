from pgvector.sqlalchemy import Vector
from sqlalchemy import Column, ForeignKey, Integer, Text
from sqlalchemy.dialects.postgresql import TSVECTOR
from sqlalchemy.orm import relationship

from app.infrastructure.database import Base


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    link_id = Column(
        Integer,
        ForeignKey("links.id", ondelete="CASCADE"),
        nullable=False,
    )
    content = Column(Text, nullable=False)
    embedding = Column(Vector(1536), nullable=False)
    tsv = Column(TSVECTOR, nullable=True)

    link = relationship("Link", back_populates="chunks")
