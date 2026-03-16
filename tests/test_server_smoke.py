from __future__ import annotations

import asyncio
from typing import Any

import pytest

from bok_ecos_mcp.config import Settings
from bok_ecos_mcp.models import SearchArgs
from bok_ecos_mcp.server import BokEcosServer


class FakeClient:
    async def statistic_table_list(self, *, start: int, end: int, lang: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "STAT_CODE": "200Y001",
                "STAT_NAME": "국내총생산",
                "CYCLE": "Q",
                "ORG_NAME": "한국은행",
            }
        ]

    async def statistic_item_list(
        self,
        *,
        table_code: str,
        start: int,
        end: int,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "STAT_CODE": table_code,
                "ITEM_NAME": "실질GDP",
                "ITEM_CODE": "1400",
                "UNIT_NAME": "십억원",
                "CYCLE": "Q",
            }
        ]

    async def statistic_search(
        self,
        *,
        args: SearchArgs,
        start: int,
        end: int,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        return [
            {
                "STAT_CODE": args.table_code,
                "TIME": args.start_date,
                "ITEM_CODE1": args.item_code1,
                "DATA_VALUE": "123.45",
                "ORG_NAME": "한국은행",
                "UNIT_NAME": "지수",
            }
        ]

    async def key_statistic_list(self, *, start: int, end: int, lang: str | None = None) -> list[dict[str, Any]]:
        return [
            {
                "CLASS_NAME": "국민소득",
                "KEYSTAT_NAME": "경제성장률",
                "DATA_VALUE": "2.1",
                "TIME": "2024",
                "CYCLE": "A",
                "UNIT_NAME": "%",
            }
        ]


class PagedFakeClient(FakeClient):
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, str | None]] = []

    async def statistic_table_list(
        self,
        *,
        start: int,
        end: int,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((start, end, lang))
        span = end - start + 1
        if start == 1:
            return [
                {
                    "STAT_CODE": "200Y001",
                    "STAT_NAME": "국내총생산",
                    "CYCLE": "Q",
                    "ORG_NAME": "한국은행",
                }
                for _ in range(span)
            ]
        return []


class ExpandingSearchFakeClient(FakeClient):
    def __init__(self) -> None:
        self.calls: list[tuple[int, int, str | None]] = []

    async def statistic_table_list(
        self,
        *,
        start: int,
        end: int,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        self.calls.append((start, end, lang))
        span = end - start + 1

        if start < 401:
            return [
                {
                    "STAT_CODE": "200Y001",
                    "STAT_NAME": "국내총생산",
                    "CYCLE": "Q",
                    "ORG_NAME": "한국은행",
                }
                for _ in range(span)
            ]

        if start >= 401 and start < 601:
            return [
                {
                    "STAT_CODE": "999Y999",
                    "STAT_NAME": "확장테이블",
                    "CYCLE": "M",
                    "ORG_NAME": "한국은행",
                }
                for _ in range(span)
            ]

        return [
            {
                "STAT_CODE": "200Y001",
                "STAT_NAME": "국내총생산",
                "CYCLE": "Q",
                "ORG_NAME": "한국은행",
            }
            for _ in range(span)
        ]


@pytest.fixture
def server() -> BokEcosServer:
    settings = Settings(ecos_api_key="test-key")
    return BokEcosServer(settings=settings, client=FakeClient())


def test_search_tables_smoke(server: BokEcosServer) -> None:
    result = asyncio.run(server.search_tables(keyword="gdp"))
    assert result["ok"] is True
    assert result["source"]["attribution"].startswith("Source:")


def test_get_series_smoke(server: BokEcosServer) -> None:
    result = asyncio.run(
        server.get_series(
        table_code="200Y001",
        item_code1="1400",
        cycle="Q",
        start_date="2024Q1",
        end_date="2024Q1",
        )
    )
    assert result["ok"] is True
    assert result["data"]["summary"]["numeric_points"] == 1
    assert result["data"]["series"][0]["value"] == 123.45


def test_resolve_query_smoke(server: BokEcosServer) -> None:
    result = asyncio.run(server.resolve_query(query="CPI 월간 최근 12개월", top_k=3))
    assert result["ok"] is True
    assert result["data"]["candidates"]


def test_get_server_info(server: BokEcosServer) -> None:
    result = asyncio.run(server.get_server_info())
    assert result["ok"] is True
    assert "search_tables" in result["data"]["tools"]
    assert "limits" in result["data"]


def test_range_guard_rejects_invalid_span(server: BokEcosServer) -> None:
    result = asyncio.run(server.get_series(
        table_code="200Y001",
        item_code1="1400",
        cycle="Q",
        start_date="2024Q1",
        end_date="2024Q4",
        start_count=1,
        end_count=server.settings.max_page_span + 1,
    ))
    assert result["ok"] is False
    assert result["data"]["error"]["code"] == "INVALID_ARGUMENT"
    assert "max allowed" in result["data"]["error"]["message"]


def test_resolve_query_top_k_cap(server: BokEcosServer) -> None:
    result = asyncio.run(server.resolve_query(query="GDP", top_k=server.settings.max_resolve_top_k + 1))
    assert result["ok"] is False
    assert result["data"]["error"]["code"] == "INVALID_ARGUMENT"
    assert "top_k must be <=" in result["data"]["error"]["message"]


def test_search_tables_fetches_full_window_when_request_is_wide(server: BokEcosServer) -> None:
    paged_client = PagedFakeClient()
    paged_server = BokEcosServer(settings=server.settings, client=paged_client)

    result = asyncio.run(
        paged_server.search_tables(
            keyword="국내총생산",
            start_count=1,
            end_count=600,
        )
    )

    assert result["ok"] is True
    assert len(paged_client.calls) >= 2
    assert len(result["data"]["tables"]) == 500
    assert paged_client.calls[0][0] == 1
    assert paged_client.calls[0][1] == 500
    assert paged_client.calls[0][2] == "kr"
    assert paged_client.calls[1][0] == 501


def test_search_tables_expands_on_empty_match(server: BokEcosServer) -> None:
    client = ExpandingSearchFakeClient()
    settings = Settings(
        ecos_api_key="test-key",
        max_page_span=800,
        table_fetch_batch_size=200,
    )
    paged_server = BokEcosServer(settings=settings, client=client)

    result = asyncio.run(
        paged_server.search_tables(
            keyword="확장테이블",
            start_count=1,
            end_count=200,
        )
    )

    assert result["ok"] is True
    assert client.calls == [
        (1, 200, "kr"),
        (1, 200, "kr"),
        (201, 400, "kr"),
        (401, 600, "kr"),
        (601, 800, "kr"),
    ]
    assert len(result["data"]["tables"]) == 200
    assert any("expanded search" in warning for warning in result["warnings"])


def test_search_tables_uses_configured_batch_size_when_set(server: BokEcosServer) -> None:
    class BatchAwareClient(FakeClient):
        def __init__(self) -> None:
            self.calls: list[tuple[int, int, str | None]] = []

        async def statistic_table_list(
            self,
            *,
            start: int,
            end: int,
            lang: str | None = None,
        ) -> list[dict[str, Any]]:
            self.calls.append((start, end, lang))
            span = end - start + 1
            return [
                {
                    "STAT_CODE": "200Y001",
                    "STAT_NAME": "국내총생산",
                    "CYCLE": "Q",
                    "ORG_NAME": "한국은행",
                }
                for _ in range(span)
            ]

    client = BatchAwareClient()
    settings = Settings(ecos_api_key="test-key", table_fetch_batch_size=150)
    paged_server = BokEcosServer(settings=settings, client=client)

    result = asyncio.run(
        paged_server.search_tables(
            keyword="국내총생산",
            start_count=1,
            end_count=500,
        )
    )

    assert result["ok"] is True
    assert client.calls == [(1, 150, "kr"), (151, 300, "kr"), (301, 450, "kr"), (451, 500, "kr")]
    assert len(result["data"]["tables"]) == 500
