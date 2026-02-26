import httpx
from bs4 import BeautifulSoup

from app.application.ports.scraper_port import ScraperPort


class ScraperRepository(ScraperPort):
    async def scrape(self, url: str) -> str:
        """OG 메타태그 기반 콘텐츠 추출."""
        headers = {"User-Agent": "Mozilla/5.0 (compatible; LinkdBot/1.0)"}
        async with httpx.AsyncClient(timeout=15.0, follow_redirects=True) as client:
            resp = await client.get(url, headers=headers)
            resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")

        og_title = soup.find("meta", property="og:title")
        og_desc = soup.find("meta", property="og:description")
        meta_desc = soup.find("meta", attrs={"name": "description"})
        title_tag = soup.find("title")

        title = (
            (og_title.get("content") if og_title else None)
            or (title_tag.string if title_tag else None)
            or ""
        )
        description = (
            (og_desc.get("content") if og_desc else None)
            or (meta_desc.get("content") if meta_desc else None)
            or ""
        )

        content = f"{title}\n\n{description}".strip()
        if not content:
            raise ValueError("페이지에서 콘텐츠를 추출할 수 없습니다.")
        return content
