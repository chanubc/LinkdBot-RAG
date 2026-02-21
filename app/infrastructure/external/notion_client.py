import httpx

from app.config import settings

_BASE = "https://api.notion.com/v1"
_VERSION = "2022-06-28"


class NotionClient:
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
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Notion-Version": _VERSION,
                },
                json={
                    "filter": {"value": "page", "property": "object"},
                    "page_size": 1,
                },
            )
            data = resp.json()
            results = data.get("results", [])
            return results[0]["id"] if results else None

    async def create_page(
        self,
        access_token: str,
        parent_page_id: str,
        title: str,
        summary: str,
        category: str,
        keywords: list[str],
        url: str,
    ) -> str:
        """Notion 페이지 생성 후 URL 반환."""
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{_BASE}/pages",
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Notion-Version": _VERSION,
                },
                json={
                    "parent": {"page_id": parent_page_id},
                    "properties": {
                        "title": {"title": [{"text": {"content": title}}]}
                    },
                    "children": [
                        _paragraph(f"🔗 URL: {url}"),
                        _paragraph(f"📂 카테고리: {category}"),
                        _paragraph(f"🔑 키워드: {', '.join(keywords)}"),
                        _paragraph(f"📝 요약:\n{summary}"),
                    ],
                },
            )
            resp.raise_for_status()
            return resp.json()["url"]


def _paragraph(text: str) -> dict:
    return {
        "object": "block",
        "type": "paragraph",
        "paragraph": {"rich_text": [{"text": {"content": text}}]},
    }
