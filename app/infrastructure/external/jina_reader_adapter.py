"""Jina Reader based scraper with OG fallback."""

import httpx

from app.application.ports.scraper_port import ScraperPort
from app.core.logger import logger
from app.infrastructure.external.scraper_client import ScraperRepository

JINA_BASE = "https://r.jina.ai/"


class JinaReaderAdapter(ScraperPort):
    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._fallback = ScraperRepository()

    async def scrape(self, url: str) -> tuple[str, str, str, str]:
        headers = {
            "Accept": "text/markdown",
            "X-Return-Format": "markdown",
        }
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        try:
            async with httpx.AsyncClient(timeout=20.0, follow_redirects=True) as client:
                resp = await client.get(f"{JINA_BASE}{url}", headers=headers)
                resp.raise_for_status()
                content = resp.text.strip()
                if not content:
                    raise ValueError("Jina Reader returned empty content")
                return content, "jina", "", ""
        except Exception as exc:
            logger.warning(
                f"Jina Reader failed for {url} ({_format_jina_error(exc)}), falling back to OG scraper"
            )
            return await self._fallback.scrape(url)


def _format_jina_error(exc: Exception) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        response = exc.response
        body = response.text.replace("\n", " ").strip()[:200]
        return f"status={response.status_code}, body={body}"
    return str(exc)
