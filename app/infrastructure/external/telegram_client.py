import html

import httpx

from app.core.config import settings
from app.application.ports.telegram_port import TelegramPort

from app.core.logger import logger


class TelegramRepository(TelegramPort):
    @property
    def _base(self) -> str:
        return f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}"

    async def send_message(self, chat_id: int, text: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/sendMessage",
                json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
            )
            if not resp.is_success:
                logger.error(
                    f"send_message failed {resp.status_code}: {resp.text} | text={text[:200]!r}"
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

    async def send_link_saved_message(
        self, chat_id: int, text: str, notion_url: str | None = None
    ) -> None:
        """링크 저장 완료 메시지 전송. notion_url이 있으면 인라인 버튼으로 추가."""
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if notion_url:
            payload["reply_markup"] = {
                "inline_keyboard": [[{"text": "📓 Notion에서 보기", "url": notion_url}]]
            }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self._base}/sendMessage", json=payload)
            if not resp.is_success:
                logger.error(
                    f"send_link_saved_message failed {resp.status_code}: {resp.text} | text={text[:200]!r}"
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
                "• Notion DB 자동 저장\n\n"
                "<b>3️⃣ 메모 저장</b>\n"
                "<code>/memo [내용]</code>\n"
                "예시: <code>/memo 오늘 배운 파이썬 팁 정리</code>\n\n"
                "<b>4️⃣ 검색</b>\n"
                "텍스트를 입력하거나 /search를 사용하면 AI로 검색해요\n"
                "<code>/search [검색어]</code> 또는 바로 입력\n"
                "예시: <code>/search 머신러닝 논문</code> 또는 <code>머신러닝 논문</code>\n\n"
                "<b>5️⃣ AI 질문</b>\n"
                "저장된 지식 기반으로 AI가 답변해드려요\n"
                "<code>/ask [질문]</code>\n"
                "예시: <code>/ask 머신러닝이란?</code>"
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

    async def send_search_results(self, chat_id: int, query: str, results: list[dict]) -> None:
        """검색 결과 전송."""
        if not results:
            await self.send_message(chat_id, f"🔍 <b>{query}</b>\n\n저장된 링크 중 관련 내용을 찾지 못했어요.")
            return

        lines = [f"🔍 <b>{html.escape(query)}</b> 검색 결과\n"]
        for i, r in enumerate(results, 1):
            title = html.escape(r.get("title") or "제목 없음")
            url = r.get("url")
            similarity = r.get("similarity", 0)
            line = f"{i}. <b>{title}</b> ({similarity:.0%})"
            if url:
                escaped_url = html.escape(url)
                line += f"\n    <a href=\"{escaped_url}\">{escaped_url}</a>"
            lines.append(line)

        await self.send_message(chat_id, "\n".join(lines))

    async def set_webhook(self, url: str) -> None:
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f"{self._base}/setWebhook",
                json={"url": url},
            )
            resp.raise_for_status()

    async def send_weekly_report(
        self,
        chat_id: int,
        text: str,
        link_id: int | None = None,
    ) -> None:
        """주간 리포트 전송. link_id 있으면 [읽음 처리] 인라인 버튼 포함."""
        payload: dict = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
        if link_id is not None:
            payload["reply_markup"] = {
                "inline_keyboard": [[
                    {"text": "✅ 읽음 처리", "callback_data": f"mark_read:{link_id}"},
                ]]
            }
        async with httpx.AsyncClient() as client:
            resp = await client.post(f"{self._base}/sendMessage", json=payload)
            resp.raise_for_status()

    async def register_commands(self) -> bool:
        """봇 명령어 자동완성 등록 (setMyCommands).

        사용자가 /를 입력할 때 명령어 목록이 자동으로 표시됩니다.
        """
        commands = [
            {"command": "start", "description": "봇 시작 및 Notion 연동"},
            {"command": "help", "description": "사용법 안내"},
            {"command": "memo", "description": "메모와 함께 링크 저장"},
            {"command": "search", "description": "저장된 링크 검색"},
            {"command": "ask", "description": "AI 에이전트에 질문"},
        ]

        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{self._base}/setMyCommands",
                    json={"commands": commands},
                )
                resp.raise_for_status()
                return True
        except Exception as e:
            logger.error(f"Failed to register Telegram commands: {e}")
            return False
