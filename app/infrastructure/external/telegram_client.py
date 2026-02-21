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

    async def send_notion_connect_button(self, chat_id: int, login_url: str) -> None:
        """Notion 연동 인라인 버튼 전송 (도움말 버튼 포함)."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base}/sendMessage",
                json={
                    "chat_id": chat_id,
                    "text": (
                        "👋 안녕하세요! <b>LinkdBot</b>입니다.\n\n"
                        "링크를 저장하고 Notion과 동기화하려면\n"
                        "아래 버튼을 눌러 Notion 계정을 연동해주세요.\n\n"
                        "사용법이 궁금하다면 <b>도움말</b> 버튼을 눌러주세요."
                    ),
                    "parse_mode": "HTML",
                    "reply_markup": {
                        "inline_keyboard": [[
                            {"text": "📖 도움말", "callback_data": "help"},
                            {"text": "🔗 Notion 연동하기", "url": login_url},
                        ]]
                    },
                },
            )

    async def answer_callback_query(self, callback_query_id: str) -> None:
        """콜백 버튼 로딩 스피너 해제."""
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{self._base}/answerCallbackQuery",
                json={"callback_query_id": callback_query_id},
            )

    async def send_help_message(self, chat_id: int) -> None:
        """전체 사용법 안내 메시지 전송."""
        await self.send_message(
            chat_id,
            (
                "📖 <b>LinkdBot 사용법</b>\n\n"
                "<b>1️⃣ Notion 연동</b>\n"
                "/start 입력 후 [Notion 연동하기] 버튼 클릭\n"
                "→ Notion 로그인 후 봇에 페이지 접근 권한 허용\n"
                "→ 연동 완료 시 텔레그램으로 알림 전송\n\n"
                "<b>2️⃣ 링크 저장</b>\n"
                "채팅창에 URL을 붙여넣으면 자동으로:\n"
                "• 페이지 내용 요약\n"
                "• 카테고리 분류\n"
                "• 키워드 추출\n"
                "• Notion 페이지 자동 생성\n\n"
                "<b>3️⃣ 링크 검색</b>\n"
                "저장한 링크를 AI로 검색하려면:\n"
                "<code>/search [검색어]</code>\n"
                "예시: <code>/search 머신러닝 논문</code>"
            ),
        )

    async def send_welcome_connected(self, chat_id: int, first_name: str | None = None) -> None:
        """Notion 이미 연동된 유저에게 사용법 안내 메시지 전송."""
        name = first_name or "사용자"
        await self.send_message(
            chat_id,
            (
                f"👋 <b>{name}</b>님, 반갑습니다!\n\n"
                "Notion 연동이 완료되어 있어요. ✅\n\n"
                "<b>사용 방법:</b>\n"
                "• 링크를 채팅창에 붙여넣으면 자동으로 저장돼요\n"
                "• AI가 요약 · 분류 · 키워드를 추출해드려요\n"
                "• 저장된 내용은 Notion에도 자동으로 동기화됩니다\n\n"
                "링크를 보내보세요! 🔗"
            ),
        )

    async def set_webhook(self, url: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/setWebhook",
                json={"url": url},
            )
            resp.raise_for_status()
