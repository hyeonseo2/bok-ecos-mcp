"""MCP resources for catalog and guidance content."""

from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from .aliases import COMMON_ALIASES
from .client import EcosClient
from .config import Settings
from .normalizers import normalize_table_rows


def register_resources(
    mcp: FastMCP,
    *,
    client: EcosClient,
    settings: Settings,
) -> None:
    """Register static and dynamic resources on the FastMCP app."""

    @mcp.resource("ecos://catalog/tables")
    async def catalog_tables() -> str:
        rows = await client.statistic_table_list(start=1, end=200, lang=settings.default_lang)
        normalized = normalize_table_rows(rows)
        return json.dumps(
            {
                "count": len(normalized),
                "tables": normalized,
                "source": {
                    "name": "Bank of Korea ECOS",
                    "attribution": "Source: Bank of Korea ECOS API (https://ecos.bok.or.kr/)",
                },
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("ecos://guide/date-formats")
    def guide_date_formats() -> str:
        guide: dict[str, Any] = {
            "A": "YYYY (예: 2024)",
            "S": "YYYY1 or YYYY2 (반기, 예: 20242)",
            "Q": "YYYYQ1..YYYYQ4 (예: 2024Q3)",
            "M": "YYYYMM (예: 202412)",
            "SM": "YYYYMM1 or YYYYMM2 (반월, 예: 2024122)",
            "D": "YYYYMMDD (예: 20241231)",
            "notes": [
                "start_date must be <= end_date",
                "Q accepts shorthand YYYY1..YYYY4 and normalizes to YYYYQn",
                "S accepts YYYYn or YYYYHn and normalizes to YYYYn",
            ],
        }
        return json.dumps(guide, ensure_ascii=False, indent=2)

    @mcp.resource("ecos://guide/attribution")
    def guide_attribution() -> str:
        return json.dumps(
            {
                "attribution": "Source: Bank of Korea ECOS API (https://ecos.bok.or.kr/)",
                "organization": "한국은행",
                "commercial_safe_mode": settings.commercial_safe_mode,
                "source_org_allowlist": list(settings.source_org_allowlist),
                "policy": "When commercial_safe_mode is enabled, rows from non-allowlisted organizations are filtered.",
            },
            ensure_ascii=False,
            indent=2,
        )

    @mcp.resource("ecos://aliases/common-series")
    def aliases_common_series() -> str:
        aliases = [
            {
                "alias": entry.alias,
                "keywords": list(entry.keywords),
                "description": entry.description,
                "default_search_args": entry.default_args.to_dict(),
            }
            for entry in COMMON_ALIASES
        ]
        return json.dumps({"aliases": aliases}, ensure_ascii=False, indent=2)
