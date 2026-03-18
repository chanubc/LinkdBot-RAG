import unittest
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock

sqlalchemy = types.ModuleType("sqlalchemy")
sqlalchemy_ext = types.ModuleType("sqlalchemy.ext")
sqlalchemy_asyncio = types.ModuleType("sqlalchemy.ext.asyncio")
sqlalchemy_asyncio.AsyncSession = object
sqlalchemy_ext.asyncio = sqlalchemy_asyncio
sqlalchemy.ext = sqlalchemy_ext
sys.modules.setdefault("sqlalchemy", sqlalchemy)
sys.modules.setdefault("sqlalchemy.ext", sqlalchemy_ext)
sys.modules.setdefault("sqlalchemy.ext.asyncio", sqlalchemy_asyncio)


def _register_stub(module_name: str, attr_name: str) -> None:
    module = types.ModuleType(module_name)
    setattr(module, attr_name, object)
    sys.modules.setdefault(module_name, module)


_register_stub("app.domain.repositories.i_chunk_repository", "IChunkRepository")
_register_stub("app.domain.repositories.i_link_repository", "ILinkRepository")
_register_stub("app.domain.repositories.i_user_repository", "IUserRepository")
_register_stub("app.application.ports.ai_analysis_port", "AIAnalysisPort")
_register_stub("app.application.ports.notion_port", "NotionPort")
_register_stub("app.application.ports.scraper_port", "ScraperPort")
_register_stub("app.application.ports.telegram_port", "TelegramPort")

httpx = types.ModuleType("httpx")
httpx.AsyncClient = object
sys.modules.setdefault("httpx", httpx)

app_core_config = types.ModuleType("app.core.config")
app_core_config.settings = SimpleNamespace(
    NOTION_REDIRECT_URI="https://example.com/notion/callback",
    NOTION_CLIENT_ID="test-client",
    NOTION_CLIENT_SECRET="test-secret",
)
sys.modules.setdefault("app.core.config", app_core_config)

from app.application.usecases.save_link_usecase import SaveLinkUseCase
from app.infrastructure.external.notion_client import _build_summary_blocks


class NotionSummaryFormatTest(unittest.TestCase):
    def test_build_summary_blocks_uses_paragraph_blocks_per_line(self):
        blocks = _build_summary_blocks("첫 줄 요약\n둘째 줄 핵심\n• 셋째 줄도 허용")

        self.assertEqual(len(blocks), 3)
        self.assertTrue(all(block["type"] == "paragraph" for block in blocks))
        self.assertEqual(
            blocks[0]["paragraph"]["rich_text"][0]["text"]["content"],
            "첫 줄 요약",
        )
        self.assertEqual(
            blocks[2]["paragraph"]["rich_text"][0]["text"]["content"],
            "셋째 줄도 허용",
        )


class SaveLinkUseCaseSummaryFormattingTest(unittest.IsolatedAsyncioTestCase):
    async def test_display_points_are_joined_without_bullet_prefixes(self):
        deps = {
            "db": AsyncMock(),
            "user_repo": AsyncMock(),
            "link_repo": AsyncMock(),
            "chunk_repo": AsyncMock(),
            "openai": AsyncMock(),
            "scraper": AsyncMock(),
            "telegram": AsyncMock(),
            "notion": AsyncMock(),
        }
        usecase = SaveLinkUseCase(**deps)

        deps["link_repo"].exists_by_user_and_url.return_value = False
        deps["scraper"].scrape.return_value = (
            "short description",
            "og",
            "OG meta description",
            "OG Page Title",
        )
        deps["openai"].analyze_content.return_value = SimpleNamespace(
            title="AI Title",
            semantic_summary="문장형 요약",
            display_points=[
                "첫 줄은 자연스러운 요약문이다.",
                "둘째 줄은 구체 정보를 담는다.",
                "셋째 줄은 추가 맥락을 담는다.",
                "넷째 줄은 일정이나 수치를 담는다.",
            ],
            category="AI",
            keywords=["a", "b", "c", "d", "e"],
        )
        deps["openai"].embed.return_value = [[0.1, 0.2]]
        deps["link_repo"].save_link.return_value = SimpleNamespace(id=123)
        deps["user_repo"].get_decrypted_token.return_value = "secret"
        deps["user_repo"].get_by_telegram_id.return_value = SimpleNamespace(
            notion_database_id="db-123"
        )
        deps["notion"].create_database_entry.return_value = "https://notion.so/page"

        await usecase.execute(telegram_id=111, url="https://example.com/post", memo=None)

        deps["notion"].create_database_entry.assert_awaited_once_with(
            access_token="secret",
            database_id="db-123",
            title="OG Page Title",
            category="AI",
            keywords=["a", "b", "c", "d", "e"],
            description="OG meta description",
            ai_summary=(
                "첫 줄은 자연스러운 요약문이다.\n"
                "둘째 줄은 구체 정보를 담는다.\n"
                "셋째 줄은 추가 맥락을 담는다.\n"
                "넷째 줄은 일정이나 수치를 담는다."
            ),
            url="https://example.com/post",
            memo=None,
        )


if __name__ == "__main__":
    unittest.main()
