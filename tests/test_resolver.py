from __future__ import annotations

from bok_ecos_mcp.resolver import QueryResolver


def test_resolve_gdp_quarterly_query() -> None:
    resolver = QueryResolver()
    result = resolver.resolve("GDP 분기 최근 4분기", top_k=3)

    assert result["candidates"]
    top = result["candidates"][0]
    assert top["alias"] == "GDP"
    assert top["search_args"]["cycle"] == "Q"
    assert top["confidence"] >= 0.6


def test_resolve_usdkrw_daily_query() -> None:
    resolver = QueryResolver()
    result = resolver.resolve("원달러 환율 일간 최근 30일", top_k=2)

    top = result["candidates"][0]
    assert top["alias"] == "USDKRW"
    assert top["search_args"]["cycle"] == "D"


def test_resolve_explicit_table_code_without_alias() -> None:
    resolver = QueryResolver()
    result = resolver.resolve("731Y001 월간", top_k=1)

    top = result["candidates"][0]
    assert top["alias"].startswith("TABLE:")
    assert top["search_args"]["table_code"] == "731Y001"
