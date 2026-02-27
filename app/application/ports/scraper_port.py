from abc import ABC, abstractmethod


class ScraperPort(ABC):
    """웹 스크래핑 Port."""

    @abstractmethod
    async def scrape(self, url: str) -> str:
        """URL에서 콘텐츠 추출."""
        pass
