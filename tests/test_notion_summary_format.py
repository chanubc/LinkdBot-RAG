import importlib
import sys
import types
import unittest
from contextlib import contextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


def _stub_module(module_name: str, **attrs: object) -> types.ModuleType:
    module = types.ModuleType(module_name)
    for key, value in attrs.items():
        setattr(module, key, value)
    return module


@contextmanager
def _scoped_summary_test_imports():
    fake_modules = {
        "sqlalchemy": _stub_module("sqlalchemy"),
        "sqlalchemy.ext": _stub_module("sqlalchemy.ext"),
        "sqlalchemy.ext.asyncio": _stub_module(
            "sqlalchemy.ext.asyncio",
            AsyncSession=object,
        ),
        "app.domain.repositories.i_chunk_repository": _stub_module(
            "app.domain.repositories.i_chunk_repository",
            IChunkRepository=object,
        ),
        "app.domain.repositories.i_link_repository": _stub_module(
            "app.domain.repositories.i_link_repository",
            ILinkRepository=object,
        ),
        "app.domain.repositories.i_user_repository": _stub_module(
            "app.domain.repositories.i_user_repository",
            IUserRepository=object,
        ),
        "app.application.ports.ai_analysis_port": _stub_module(
            "app.application.ports.ai_analysis_port",
            AIAnalysisPort=object,
        ),
        "app.application.ports.notion_port": _stub_module(
            "app.application.ports.notion_port",
            NotionPort=object,
        ),
        "app.application.ports.scraper_port": _stub_module(
            "app.application.ports.scraper_port",
            ScraperPort=object,
        ),
        "app.application.ports.telegram_port": _stub_module(
            "app.application.ports.telegram_port",
            TelegramPort=object,
        ),
        "httpx": _stub_module("httpx", AsyncClient=object),
        "app.core.config": _stub_module(
            "app.core.config",
            settings=SimpleNamespace(
                NOTION_REDIRECT_URI="https://example.com/notion/callback",
                NOTION_CLIENT_ID="test-client",
                NOTION_CLIENT_SECRET="test-secret",
            ),
        ),
    }
    fake_modules["sqlalchemy"].ext = fake_modules["sqlalchemy.ext"]
    fake_modules["sqlalchemy.ext"].asyncio = fake_modules["sqlalchemy.ext.asyncio"]

    target_modules = [
        "app.infrastructure.external.notion_client",
        "app.application.usecases.save_link_usecase",
    ]
    originals = {name: sys.modules.get(name) for name in fake_modules}
    target_originals = {name: sys.modules.get(name) for name in target_modules}

    for name in [*fake_modules, *target_modules]:
        sys.modules.pop(name, None)

    try:
        with patch.dict(sys.modules, fake_modules, clear=False):
            notion_client = importlib.import_module("app.infrastructure.external.notion_client")
            save_link_usecase = importlib.import_module(
                "app.application.usecases.save_link_usecase"
            )
            yield notion_client, save_link_usecase.SaveLinkUseCase
    finally:
        for name in [*fake_modules, *target_modules]:
            sys.modules.pop(name, None)
        for name, module in {**originals, **target_originals}.items():
            if module is not None:
                sys.modules[name] = module


class NotionSummaryFormatTest(unittest.TestCase):
    def test_build_summary_blocks_uses_paragraph_blocks_per_line(self):
        with _scoped_summary_test_imports() as (notion_client, _):
            blocks = notion_client._build_summary_blocks("첫 줄 요약\n둘째 줄 핵심\n• 셋째 줄도 허용")

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

    def test_build_summary_blocks_splits_long_lines(self):
        with _scoped_summary_test_imports() as (notion_client, _):
            long_line = "A" * 4300
            blocks = notion_client._build_summary_blocks(long_line)

        self.assertEqual(len(blocks), 3)
        self.assertEqual(len(blocks[0]["paragraph"]["rich_text"][0]["text"]["content"]), 2000)
        self.assertEqual(len(blocks[1]["paragraph"]["rich_text"][0]["text"]["content"]), 2000)
        self.assertEqual(len(blocks[2]["paragraph"]["rich_text"][0]["text"]["content"]), 300)


class SaveLinkUseCaseSummaryFormattingTest(unittest.IsolatedAsyncioTestCase):
    async def test_semantic_summary_is_sent_to_notion_body(self):
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

        with _scoped_summary_test_imports() as (_, save_link_usecase_cls):
            usecase = save_link_usecase_cls(**deps)

        deps["link_repo"].exists_by_user_and_url.return_value = False
        deps["scraper"].scrape.return_value = (
            "short description",
            "og",
            "OG meta description",
            "OG Page Title",
        )
        deps["openai"].analyze_content.return_value = SimpleNamespace(
            title="AI Title",
            semantic_summary="문장형 요약이다. 핵심 맥락과 중요한 정보를 자연스럽게 설명한다.",
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
            ai_summary="문장형 요약이다. 핵심 맥락과 중요한 정보를 자연스럽게 설명한다.",
            url="https://example.com/post",
            memo=None,
        )


if __name__ == "__main__":
    unittest.main()
