from __future__ import annotations

import asyncio
from typing import Any

import httpx
import pytest

from bok_ecos_mcp.client import EcosClient
from bok_ecos_mcp.config import Settings
from bok_ecos_mcp.errors import EcosAPIError, EcosRateLimitError
from bok_ecos_mcp.models import SearchArgs


@pytest.fixture
def settings() -> Settings:
    return Settings(ecos_api_key="test-key")


def test_build_url_statistic_search(settings: Settings) -> None:
    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={})

    client = EcosClient(
        settings=settings,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )
    url = client._build_url(
        "StatisticSearch",
        start=1,
        end=100,
        lang="kr",
        segments=("200Y001", "Q", "2024Q1", "2024Q4", "1400", "?", "?", "?"),
    )
    assert (
        url
        == "https://ecos.bok.or.kr/api/StatisticSearch/test-key/json/kr/1/100/"
        "200Y001/Q/2024Q1/2024Q4/1400/%3F/%3F/%3F"
    )


def test_statistic_table_list_parses_rows(settings: Settings) -> None:
    payload: dict[str, Any] = {
        "StatisticTableList": {
            "list_total_count": 1,
            "RESULT": {"CODE": "INFO-000", "MESSAGE": "ok"},
            "row": [{"STAT_CODE": "200Y001", "STAT_NAME": "GDP"}],
        }
    }

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = EcosClient(settings=settings, http_client=async_client)

    rows = asyncio.run(client.statistic_table_list(start=1, end=10))

    assert len(rows) == 1
    assert rows[0]["STAT_CODE"] == "200Y001"
    asyncio.run(async_client.aclose())


def test_statistic_search_uses_segments(settings: Settings) -> None:
    captured_urls: list[str] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        captured_urls.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "StatisticSearch": {
                    "RESULT": {"CODE": "INFO-000", "MESSAGE": "ok"},
                    "row": [{"TIME": "2024Q1", "DATA_VALUE": "1.0"}],
                }
            },
        )

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = EcosClient(settings=settings, http_client=async_client)

    args = SearchArgs(
        table_code="200Y001",
        cycle="Q",
        start_date="2024Q1",
        end_date="2024Q1",
        item_code1="1400",
    )
    rows = asyncio.run(client.statistic_search(args=args))

    assert rows
    assert captured_urls
    assert "StatisticSearch" in captured_urls[0]
    assert "200Y001/Q/2024Q1/2024Q1/1400" in captured_urls[0]
    asyncio.run(async_client.aclose())


def test_statistic_request_exhaust_retries_as_api_error(settings: Settings) -> None:
    settings = Settings(
        ecos_api_key="test-key",
        max_retries=1,
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=503, json={"RESULT": {"CODE": "FAIL", "MESSAGE": "retry"}})

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = EcosClient(settings=settings, http_client=async_client)

    with pytest.raises(EcosAPIError):
        asyncio.run(client.statistic_table_list(start=1, end=1))
    asyncio.run(async_client.aclose())


def test_statistic_request_exhaust_retries_as_rate_limit(settings: Settings) -> None:
    settings = Settings(
        ecos_api_key="test-key",
        max_retries=1,
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(status_code=429, json={"RESULT": {"CODE": "FAIL", "MESSAGE": "throttle"}})

    async_client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = EcosClient(settings=settings, http_client=async_client)

    with pytest.raises(EcosRateLimitError):
        asyncio.run(client.statistic_table_list(start=1, end=1))
    asyncio.run(async_client.aclose())
