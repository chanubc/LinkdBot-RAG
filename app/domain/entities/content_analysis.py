from typing import Literal

from pydantic import BaseModel

CategoryType = Literal[
    "AI", "Dev", "Career", "Business", "Science",
    "Design", "Health", "Productivity", "Education",
    "Other",
]


class ContentAnalysis(BaseModel):
    title: str
    semantic_summary: str       # 임베딩/DB용 (4~6문장, 고유명사/맥락 보존)
    display_points: list[str]   # Notion 본문용 짧은 요약 라인 (4~5개)
    category: CategoryType
    keywords: list[str]
