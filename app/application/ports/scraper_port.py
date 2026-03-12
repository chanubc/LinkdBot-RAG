from abc import ABC, abstractmethod


class ScraperPort(ABC):
    """웹 스크래핑 Port."""

    @abstractmethod
    async def scrape(self, url: str) -> tuple[str, str, str]:
        """URL에서 콘텐츠 추출.

        Returns:
            (content, source, og_description) — source는 "og" | "jina" 등 수집 방법 식별자.
        """
        pass
