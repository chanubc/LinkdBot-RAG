from unittest.mock import AsyncMock
from unittest.mock import patch

import httpx
import pytest

from app.infrastructure.external.jina_reader_adapter import JinaReaderAdapter


@pytest.mark.asyncio
async def test_jina_failure_logs_status_and_body_snippet():
    adapter = JinaReaderAdapter(api_key="test-key")
    adapter._fallback.scrape = AsyncMock(return_value=("fallback content", "og", "desc", "title"))

    request = httpx.Request("GET", "https://r.jina.ai/https://example.com/article")
    response = httpx.Response(
        502,
        request=request,
        text="upstream bad gateway from jina edge",
    )
    exc = httpx.HTTPStatusError("bad gateway", request=request, response=response)

    with patch("app.infrastructure.external.jina_reader_adapter.httpx.AsyncClient.get", new=AsyncMock(side_effect=exc)):
        with patch("app.infrastructure.external.jina_reader_adapter.logger.warning") as mock_warning:
            result = await adapter.scrape("https://example.com/article")

    assert result == ("fallback content", "og", "desc", "title")
    mock_warning.assert_called_once()
    message = mock_warning.call_args.args[0]
    assert "status=502" in message
    assert "upstream bad gateway from jina edge" in message
    assert "https://example.com/article" in message
