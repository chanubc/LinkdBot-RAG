from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class KnowledgeSource:
    """Domain entity: source of knowledge from retrieved documents."""
    title: str
    url: str | None = None
    link_id: int | None = None
