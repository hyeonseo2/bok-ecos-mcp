"""FastMCP stdio server for Bank of Korea ECOS."""

from __future__ import annotations

import logging
import os
import sys
from typing import Any

from mcp.server.fastmcp import FastMCP

from .client import EcosClient
from .config import Settings
from .errors import ConfigError, EcosAPIError, EcosNetworkError, EcosRateLimitError, EcosValidationError
from .models import SearchArgs
from .normalizers import (
    filter_rows_by_allowlist,
    make_envelope,
    make_error_envelope,
    normalize_item_rows,
    normalize_key_stat_rows,
    normalize_series_rows,
    normalize_table_rows,
    validate_date_range,
)
from .resolver import QueryResolver
from .resources import register_resources

logger = logging.getLogger(__name__)


class BokEcosServer:
    """High-level server wrapper exposing both tool methods and FastMCP app."""

    def __init__(
        self,
        *,
        settings: Settings,
        client: EcosClient | None = None,
        resolver: QueryResolver | None = None,
        host: str = "127.0.0.1",
        port: int = 8000,
    ) -> None:
        self.settings = settings
        self.client = client or EcosClient(settings)
        self.resolver = resolver or QueryResolver()
        self.mcp = FastMCP("bok-ecos-mcp", host=host, port=port)
        self._register_tools()
        register_resources(self.mcp, client=self.client, settings=self.settings)

    def _register_tools(self) -> None:
        server = self

        @self.mcp.tool(
            description="통계표 목록에서 키워드로 테이블을 검색합니다. 시작/끝 인덱스로 조회 범위를 지정하고, 기간 필터 없이 테이블명/코드/기관명 문자열 기반으로 부분일치 검색합니다.",
        )
        async def search_tables(
            keyword: str,
            start_count: int = 1,
            end_count: int = 300,
            lang: str | None = None,
        ) -> dict[str, Any]:
            """search_tables(tool) - keyword 기반으로 ECOS table_code 목록 조회"""
            return await server.search_tables(
                keyword=keyword,
                start_count=start_count,
                end_count=end_count,
                lang=lang,
            )

        @self.mcp.tool(
            description="특정 통계표(table_code) 내 항목(item)을 조회합니다. 시리즈 조회 전에 item_code 후보를 찾을 때 사용합니다.",
        )
        async def list_table_items(
            table_code: str,
            start_count: int = 1,
            end_count: int = 1000,
            lang: str | None = None,
        ) -> dict[str, Any]:
            """list_table_items(tool) - table_code 기준 항목 목록 조회"""
            return await server.list_table_items(
                table_code=table_code,
                start_count=start_count,
                end_count=end_count,
                lang=lang,
            )

        @self.mcp.tool(
            description="특정 통계표의 시계열을 조회합니다. table_code/item_code1/period로 시계열 값 배열과 요약 통계를 반환합니다.",
        )
        async def get_series(
            table_code: str,
            item_code1: str,
            cycle: str,
            start_date: str,
            end_date: str,
            item_code2: str = "?",
            item_code3: str = "?",
            org_code: str = "?",
            start_count: int = 1,
            end_count: int = 1000,
            lang: str | None = None,
        ) -> dict[str, Any]:
            """get_series(tool) - table_code/item_code 기반 시계열 조회"""
            return await server.get_series(
                table_code=table_code,
                item_code1=item_code1,
                cycle=cycle,
                start_date=start_date,
                end_date=end_date,
                item_code2=item_code2,
                item_code3=item_code3,
                org_code=org_code,
                start_count=start_count,
                end_count=end_count,
                lang=lang,
            )

        @self.mcp.tool(
            description="ECOS 주요지표(key statistics) 목록을 조회합니다. 시점별 핵심 지표(환율/금리/물가지표 등) 값을 간단하게 확인할 때 사용합니다.",
        )
        async def get_key_statistics(
            start_count: int = 1,
            end_count: int = 100,
            lang: str | None = None,
        ) -> dict[str, Any]:
            """get_key_statistics(tool) - 핵심 통계 지표 목록 조회"""
            return await server.get_key_statistics(
                start_count=start_count,
                end_count=end_count,
                lang=lang,
            )

        @self.mcp.tool(
            description="자연어 질의(예: '원달러 환율 최근 30일')를 ECOS 검색/조회 인자로 해석해 후보를 반환합니다.",
        )
        async def resolve_query(query: str, top_k: int = 5) -> dict[str, Any]:
            """resolve_query(tool) - 자연어 질의를 검색 후보로 변환"""
            return await server.resolve_query(query=query, top_k=top_k)

        @self.mcp.tool(
            description="서버 상태, 제한치, 캐시 TTL, 사용 가능 tools/resources 같은 런타임 메타정보를 반환합니다.",
        )
        async def get_server_info() -> dict[str, Any]:
            """get_server_info(tool) - 서버 메타/설정 정보 반환"""
            return await server.get_server_info()

    def _validate_range(
        self,
        *,
        label: str,
        start_count: int,
        end_count: int,
    ) -> None:
        if start_count < 1:
            raise EcosValidationError(f"{label}: start_count must be >= 1")
        if end_count < start_count:
            raise EcosValidationError(f"{label}: end_count must be >= start_count")
        span = end_count - start_count + 1
        if span > self.settings.max_page_span:
            raise EcosValidationError(
                f"{label}: requested span {span} exceeds max allowed {self.settings.max_page_span}"
            )

    async def _fetch_table_pages(
        self,
        *,
        start_count: int,
        end_count: int,
        lang: str | None,
    ) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        cursor = start_count
        effective_lang = lang or self.settings.default_lang

        while cursor <= end_count:
            batch_size = self.settings.table_fetch_batch_size
            window_end = min(cursor + batch_size - 1, end_count)
            page_rows = await self.client.statistic_table_list(
                start=cursor,
                end=window_end,
                lang=effective_lang,
            )
            rows.extend(page_rows)
            expected_window_size = window_end - cursor + 1
            if len(page_rows) < expected_window_size:
                break
            cursor = window_end + 1

        return rows

    async def search_tables(
        self,
        *,
        keyword: str,
        start_count: int = 1,
        end_count: int = 300,
        lang: str | None = None,
    ) -> dict[str, Any]:
        request = {
            "keyword": keyword,
            "start_count": start_count,
            "end_count": end_count,
            "lang": lang or self.settings.default_lang,
        }
        try:
            if not keyword.strip():
                raise EcosValidationError("keyword must not be empty")
            self._validate_range(
                label="search_tables",
                start_count=start_count,
                end_count=end_count,
            )

            rows = await self._fetch_table_pages(
                start_count=start_count,
                end_count=end_count,
                lang=lang,
            )
            filtered_rows, warnings = filter_rows_by_allowlist(
                rows,
                allowlist=self.settings.source_org_allowlist,
                enabled=self.settings.commercial_safe_mode,
            )
            lowered_keyword = keyword.lower()
            matched = [
                row
                for row in filtered_rows
                if lowered_keyword in str(row.get("STAT_NAME", "")).lower()
                or lowered_keyword in str(row.get("STAT_CODE", "")).lower()
            ]

            if not matched and end_count < self.settings.max_page_span:
                expanded_end_count = self.settings.max_page_span
                expanded_rows = await self._fetch_table_pages(
                    start_count=start_count,
                    end_count=expanded_end_count,
                    lang=lang,
                )
                expanded_filtered_rows, expanded_warnings = filter_rows_by_allowlist(
                    expanded_rows,
                    allowlist=self.settings.source_org_allowlist,
                    enabled=self.settings.commercial_safe_mode,
                )
                expanded_matched = [
                    row
                    for row in expanded_filtered_rows
                    if lowered_keyword in str(row.get("STAT_NAME", "")).lower()
                    or lowered_keyword in str(row.get("STAT_CODE", "")).lower()
                ]
                warnings.extend(expanded_warnings)
                if expanded_matched:
                    warnings.append(
                        f"No matches in requested range ({start_count}..{end_count}); "
                        f"expanded search up to {expanded_end_count}."
                    )
                    filtered_rows = expanded_filtered_rows
                    matched = expanded_matched

            normalized = normalize_table_rows(matched)
            return make_envelope(
                ok=True,
                request=request,
                data={"count": len(normalized), "tables": normalized},
                transformed_fields=[
                    "tables[].table_code",
                    "tables[].table_name",
                    "tables[].cycle",
                    "tables[].org_name",
                ],
                warnings=warnings,
            )
        except EcosValidationError as exc:
            return make_error_envelope(
                request=request,
                error_code="INVALID_ARGUMENT",
                message=str(exc),
            )
        except EcosRateLimitError as exc:
            return make_error_envelope(
                request=request,
                error_code="RATE_LIMIT",
                message=str(exc),
            )
        except (EcosAPIError, EcosNetworkError) as exc:
            logger.exception("search_tables failed")
            return make_error_envelope(
                request=request,
                error_code="UPSTREAM_ERROR",
                message=str(exc),
            )

    async def list_table_items(
        self,
        *,
        table_code: str,
        start_count: int = 1,
        end_count: int = 1000,
        lang: str | None = None,
    ) -> dict[str, Any]:
        request = {
            "table_code": table_code,
            "start_count": start_count,
            "end_count": end_count,
            "lang": lang or self.settings.default_lang,
        }
        try:
            if not table_code.strip():
                raise EcosValidationError("table_code must not be empty")
            self._validate_range(
                label="list_table_items",
                start_count=start_count,
                end_count=end_count,
            )

            rows = await self.client.statistic_item_list(
                table_code=table_code,
                start=start_count,
                end=end_count,
                lang=lang,
            )
            normalized = normalize_item_rows(rows)
            return make_envelope(
                ok=True,
                request=request,
                data={"count": len(normalized), "items": normalized},
                transformed_fields=[
                    "items[].item_code",
                    "items[].item_name",
                    "items[].unit_name",
                    "items[].cycle",
                ],
            )
        except EcosValidationError as exc:
            return make_error_envelope(
                request=request,
                error_code="INVALID_ARGUMENT",
                message=str(exc),
            )
        except EcosRateLimitError as exc:
            return make_error_envelope(
                request=request,
                error_code="RATE_LIMIT",
                message=str(exc),
            )
        except (EcosAPIError, EcosNetworkError) as exc:
            logger.exception("list_table_items failed")
            return make_error_envelope(
                request=request,
                error_code="UPSTREAM_ERROR",
                message=str(exc),
            )

    async def get_series(
        self,
        *,
        table_code: str,
        item_code1: str,
        cycle: str,
        start_date: str,
        end_date: str,
        item_code2: str = "?",
        item_code3: str = "?",
        org_code: str = "?",
        start_count: int = 1,
        end_count: int = 1000,
        lang: str | None = None,
    ) -> dict[str, Any]:
        request = {
            "table_code": table_code,
            "item_code1": item_code1,
            "item_code2": item_code2,
            "item_code3": item_code3,
            "org_code": org_code,
            "cycle": cycle,
            "start_date": start_date,
            "end_date": end_date,
            "start_count": start_count,
            "end_count": end_count,
            "lang": lang or self.settings.default_lang,
        }

        try:
            if not table_code.strip() or not item_code1.strip():
                raise EcosValidationError("table_code and item_code1 are required")
            self._validate_range(
                label="get_series",
                start_count=start_count,
                end_count=end_count,
            )

            normalized_cycle, normalized_start, normalized_end = validate_date_range(
                cycle,
                start_date,
                end_date,
            )

            search_args = SearchArgs(
                table_code=table_code.strip(),
                cycle=normalized_cycle,
                start_date=normalized_start,
                end_date=normalized_end,
                item_code1=item_code1.strip(),
                item_code2=item_code2.strip() or "?",
                item_code3=item_code3.strip() or "?",
                org_code=org_code.strip() or "?",
            )
            rows = await self.client.statistic_search(
                args=search_args,
                start=start_count,
                end=end_count,
                lang=lang,
            )
            filtered_rows, warnings = filter_rows_by_allowlist(
                rows,
                allowlist=self.settings.source_org_allowlist,
                enabled=self.settings.commercial_safe_mode,
            )
            normalized_series = normalize_series_rows(filtered_rows)

            numeric_values = [
                entry["value"] for entry in normalized_series if isinstance(entry.get("value"), float)
            ]
            summary = {
                "points": len(normalized_series),
                "numeric_points": len(numeric_values),
                "min": min(numeric_values) if numeric_values else None,
                "max": max(numeric_values) if numeric_values else None,
            }
            return make_envelope(
                ok=True,
                request=request,
                data={
                    "series": normalized_series,
                    "summary": summary,
                    "search_args": search_args.to_dict(),
                },
                transformed_fields=[
                    "series[].time",
                    "series[].value_raw",
                    "series[].value",
                    "summary",
                ],
                warnings=warnings,
            )
        except EcosValidationError as exc:
            return make_error_envelope(
                request=request,
                error_code="INVALID_ARGUMENT",
                message=str(exc),
            )
        except EcosRateLimitError as exc:
            return make_error_envelope(
                request=request,
                error_code="RATE_LIMIT",
                message=str(exc),
            )
        except (EcosAPIError, EcosNetworkError) as exc:
            logger.exception("get_series failed")
            return make_error_envelope(
                request=request,
                error_code="UPSTREAM_ERROR",
                message=str(exc),
            )

    async def get_key_statistics(
        self,
        *,
        start_count: int = 1,
        end_count: int = 100,
        lang: str | None = None,
    ) -> dict[str, Any]:
        request = {
            "start_count": start_count,
            "end_count": end_count,
            "lang": lang or self.settings.default_lang,
        }
        try:
            self._validate_range(
                label="get_key_statistics",
                start_count=start_count,
                end_count=end_count,
            )
            rows = await self.client.key_statistic_list(
                start=start_count,
                end=end_count,
                lang=lang,
            )
            normalized = normalize_key_stat_rows(rows)
            return make_envelope(
                ok=True,
                request=request,
                data={"count": len(normalized), "statistics": normalized},
                transformed_fields=[
                    "statistics[].key_stat_name",
                    "statistics[].time",
                    "statistics[].value_raw",
                    "statistics[].value",
                ],
            )
        except EcosValidationError as exc:
            return make_error_envelope(
                request=request,
                error_code="INVALID_ARGUMENT",
                message=str(exc),
            )
        except EcosRateLimitError as exc:
            return make_error_envelope(
                request=request,
                error_code="RATE_LIMIT",
                message=str(exc),
            )
        except (EcosAPIError, EcosNetworkError) as exc:
            logger.exception("get_key_statistics failed")
            return make_error_envelope(
                request=request,
                error_code="UPSTREAM_ERROR",
                message=str(exc),
            )

    async def resolve_query(self, *, query: str, top_k: int = 5) -> dict[str, Any]:
        request = {"query": query, "top_k": top_k}
        try:
            if not query.strip():
                raise EcosValidationError("query must not be empty")
            if top_k < 1:
                raise EcosValidationError("top_k must be >= 1")
            if top_k > self.settings.max_resolve_top_k:
                raise EcosValidationError(
                    f"top_k must be <= {self.settings.max_resolve_top_k}"
                )
            resolved = self.resolver.resolve(query=query, top_k=top_k)
            return make_envelope(
                ok=True,
                request=request,
                data=resolved,
                transformed_fields=["candidates[].score", "candidates[].confidence", "search_args"],
                warnings=resolved.get("warnings", []),
            )
        except EcosValidationError as exc:
            return make_error_envelope(
                request=request,
                error_code="INVALID_ARGUMENT",
                message=str(exc),
            )

    async def get_server_info(self) -> dict[str, Any]:
        request: dict[str, Any] = {}
        data = {
            "name": "bok-ecos-mcp",
            "version": "0.1.0",
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "transport": os.getenv("BOK_ECOS_TRANSPORT", "stdio"),
            "safe_mode": {
                "commercial_safe_mode": self.settings.commercial_safe_mode,
                "source_org_allowlist": list(self.settings.source_org_allowlist),
            },
            "cache_ttl_seconds": {
                "table_list": self.settings.cache_ttl_table_list,
                "item_list": self.settings.cache_ttl_item_list,
                "series": self.settings.cache_ttl_series,
                "key_stats": self.settings.cache_ttl_key_stats,
            },
            "limits": {
                "max_page_span": self.settings.max_page_span,
                "max_resolve_top_k": self.settings.max_resolve_top_k,
                "table_fetch_batch_size": self.settings.table_fetch_batch_size,
            },
            "tools": [
                "search_tables",
                "list_table_items",
                "get_series",
                "get_key_statistics",
                "resolve_query",
                "get_server_info",
            ],
            "resources": [
                "ecos://catalog/tables",
                "ecos://guide/date-formats",
                "ecos://guide/attribution",
                "ecos://aliases/common-series",
            ],
        }
        return make_envelope(
            ok=True,
            request=request,
            data=data,
            transformed_fields=["safe_mode", "cache_ttl_seconds", "limits", "tools", "resources"],
        )


def create_server(
    settings: Settings | None = None,
    *,
    client: EcosClient | None = None,
    resolver: QueryResolver | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> BokEcosServer:
    runtime_settings = settings or Settings.from_env(require_api_key=True)
    return BokEcosServer(
        settings=runtime_settings,
        client=client,
        resolver=resolver,
        host=host,
        port=port,
    )


def _parse_int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc


def create_app(
    settings: Settings | None = None,
    *,
    client: EcosClient | None = None,
    resolver: QueryResolver | None = None,
    host: str = "127.0.0.1",
    port: int = 8000,
) -> FastMCP:
    server = create_server(settings=settings, client=client, resolver=resolver, host=host, port=port)
    return server.mcp


def _normalize_transport(value: str) -> str:
    normalized = value.strip().lower().replace("_", "-")
    if normalized in {"stdio", "streamable-http", "streamable_http"}:
        return "streamable-http" if normalized == "streamable_http" else normalized
    raise ConfigError(
        "Unsupported transport. Supported values are: stdio, streamable-http"
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        stream=sys.stderr,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    try:
        transport = _normalize_transport(os.getenv("BOK_ECOS_TRANSPORT", "stdio"))
        host = os.getenv("BOK_ECOS_HOST", "127.0.0.1")
        port = _parse_int_env("BOK_ECOS_PORT", 8000)
        app = create_app(host=host, port=port)
        app.run(transport=transport)
    except ConfigError:
        logger.exception("Failed to initialize server due to configuration error")
        raise


if __name__ == "__main__":
    main()
