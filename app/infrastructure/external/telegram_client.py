import httpx

from app.config import settings


class TelegramClient:
    @property
    def _base(self) -> str:
        return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

    async def send_message(self, chat_id: int, text: str) -> None:
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )

    async def send_notion_connect_button(self, chat_id: int, telegram_id: int) -> None:
        """Notion 연동 인라인 버튼 전송."""
        # NOTION_REDIRECT_URI: .../auth/notion/callback → .../auth/notion/login
        login_url = (
            settings.NOTION_REDIRECT_URI.replace("/callback", "/login")
            + f"?telegram_id={telegram_id}"
        )
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        "👋 안녕하세요! <b>LinkdBot</b>입니다.\n\n"
                        "링크를 저장하고 Notion과 동기화하려면\n"
                        "아래 버튼을 눌러 Notion 계정을 연동해주세요."
                    ),
                    "parse_mode": "HTML",
                    "reply_markup": {
                        "inline_keyboard": [[
                            {"text": "🔗 Notion 연동하기", "url": login_url}
                        ]]
                    },
                },
            )

    async def set_webhook(self, url: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/setWebhook",
                json={"url": url},
            )
            resp.raise_for_status()
