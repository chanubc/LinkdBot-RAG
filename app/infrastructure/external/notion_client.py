from datetime import datetime, timezone

import httpx

from app.core.config import settings
from app.application.ports.notion_port import NotionPort

_BASE = "https://api.notion.com/v1"
_VERSION = "2022-06-28"


class NotionRepository(NotionPort):
    async def exchange_code(self, code: str) -> dict:
        """OAuth authorization code → access token 교환."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/oauth/token",
                json={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": settings.NOTION_REDIRECT_URI,
                },
                auth=(settings.NOTION_CLIENT_ID, settings.NOTION_CLIENT_SECRET),
            )
            resp.raise_for_status()
            return resp.json()

    async def get_accessible_page_id(self, access_token: str) -> str | None:
        """봇이 접근 가능한 첫 번째 페이지 ID 반환."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/search",
                headers=_headers(access_token),
                json={
                    "filter": {"value": "page", "property": "object"},
                    "page_size": 1,
                },
            )
            resp.raise_for_status()
            data = resp.json()
            results = data.get("results", [])
            return results[0]["id"] if results else None

    async def create_database(self, access_token: str, parent_page_id: str) -> str:
        """LinkdBot 전용 Notion 데이터베이스 생성 후 database_id 반환."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/databases",
                headers=_headers(access_token),
                json={
                    "parent": {"type": "page_id", "page_id": parent_page_id},
                    "title": [{"type": "text", "text": {"content": "LinkdBot"}}],
                    "properties": {
                        "Name":     {"title": {}},
                        "URL":      {"url": {}},
                        "Category": {"select": {}},
                        "Keywords": {"multi_select": {}},
                        "Summary":  {"rich_text": {}},
                        "Memo":     {"rich_text": {}},
                        "Date":     {"date": {}},
                    },
                },
            )
            resp.raise_for_status()
            return resp.json()["id"]

    async def create_database_entry(
        self,
        access_token: str,
        database_id: str,
        title: str,
        category: str,
        keywords: list[str],
        summary: str,
        url: str | None = None,
        memo: str | None = None,
    ) -> str:
        """Notion DB에 행 추가 후 페이지 URL 반환."""
        properties: dict = {
            "Name":     {"title": [{"text": {"content": title[:2000]}}]},
            "Category": {"select": {"name": category[:100]}},
            "Keywords": {"multi_select": [{"name": kw[:100]} for kw in keywords]},
            "Summary":  {"rich_text": [{"text": {"content": summary[:2000]}}]},
            "Date":     {"date": {"start": datetime.now(timezone.utc).date().isoformat()}},
        }
        if url:
            properties["URL"] = {"url": url}
        if memo:
            properties["Memo"] = {"rich_text": [{"text": {"content": memo[:2000]}}]}

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/pages",
                headers=_headers(access_token),
                json={
                    "parent": {"database_id": database_id},
                    "properties": properties,
                },
            )
            resp.raise_for_status()
            return resp.json()["url"]


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": _VERSION,
    }
