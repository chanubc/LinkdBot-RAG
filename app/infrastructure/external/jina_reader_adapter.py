"""Jina Reader 기반 스크래퍼 — Markdown 전문 추출.

Jina Reader API: https://r.jina.ai/{url}
Bearer 토큰 없이도 기본 동작하나, API 키 있으면 Rate Limit 완화.
실패 시 OG 메타태그 기반 ScraperRepository로 폴백.
"""
import httpx

from app.application.ports.scraper_port import ScraperPort
from app.infrastructure.external.scraper_client import ScraperRepository

from app.core.logger import logger

JINA_BASE = "https://r.jina.ai/"


class JinaReaderAdapter(ScraperPort):
    """Jina Reader로 Markdown 전문 추출. 실패 시 OG 스크래퍼로 폴백."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        self._fallback = ScraperRepository()

    async def scrape(self, url: str) -> tuple[str, str, str]:
        """Jina Reader로 콘텐츠 추출.

        Returns:
            (content, "jina", "") 성공 시, 실패 시 폴백 ScraperRepository 결과 반환.
        """
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
            logger.warning(f"Jina Reader failed for {url} ({exc}), falling back to OG scraper")
            return await self._fallback.scrape(url)
