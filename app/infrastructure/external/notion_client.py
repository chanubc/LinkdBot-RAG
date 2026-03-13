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
        description: str,
        ai_summary: str | None = None,
        url: str | None = None,
        memo: str | None = None,
    ) -> str:
        """Notion DB에 행 추가 후 페이지 URL 반환.

        ai_summary는 페이지 본문(children 블록)에 bullet 형태로 삽입됨.
        """
        properties: dict = {
            "Name":     {"title": [{"text": {"content": title[:2000]}}]},
            "Category": {"select": {"name": category[:100]}},
            "Keywords": {"multi_select": [{"name": kw[:100]} for kw in keywords]},
            "Summary":  {"rich_text": [{"text": {"content": description[:2000]}}]},
            "Date":     {"date": {"start": datetime.now(timezone.utc).date().isoformat()}},
        }
        if url:
            properties["URL"] = {"url": url}
        if memo:
            properties["Memo"] = {"rich_text": [{"text": {"content": memo[:2000]}}]}

        children = _build_summary_blocks(ai_summary) if ai_summary else []

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/pages",
                headers=_headers(access_token),
                json={
                    "parent": {"database_id": database_id},
                    "properties": properties,
                    "children": children,
                },
            )
            resp.raise_for_status()
            return resp.json()["url"]


def _build_summary_blocks(ai_summary: str) -> list[dict]:
    """AI bullet 요약 문자열을 Notion bulleted_list_item 블록 배열로 변환."""
    blocks = []
    for line in ai_summary.splitlines():
        text = line.lstrip("•").strip()
        if not text:
            continue
        blocks.append({
            "object": "block",
            "type": "bulleted_list_item",
            "bulleted_list_item": {
                "rich_text": [{"type": "text", "text": {"content": text[:2000]}}]
            },
        })
    return blocks


def _headers(access_token: str) -> dict:
    return {
        "Authorization": f"Bearer {access_token}",
        "Notion-Version": _VERSION,
    }
