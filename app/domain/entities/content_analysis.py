from typing import Literal

from pydantic import BaseModel

CategoryType = Literal["AI", "Dev", "Career", "Business", "Science", "Other"]


class ContentAnalysis(BaseModel):
    title: str
    summary: str
    category: CategoryType
    keywords: list[str]
