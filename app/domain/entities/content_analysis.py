from typing import Literal

from pydantic import BaseModel

CategoryType = Literal[
    "AI", "Dev", "Career", "Business", "Science",
    "Design", "Health", "Productivity", "Education",
    "Other",
]


class ContentAnalysis(BaseModel):
    title: str
    semantic_summary: str       # DB/임베딩/Notion 본문 공용 요약 문단
    category: CategoryType
    keywords: list[str]
