"""Common series aliases for Korean macro/financial indicators."""

from __future__ import annotations

from dataclasses import dataclass

from .models import SearchArgs


@dataclass(frozen=True, slots=True)
class AliasEntry:
    alias: str
    keywords: tuple[str, ...]
    default_args: SearchArgs
    description: str


COMMON_ALIASES: tuple[AliasEntry, ...] = (
    AliasEntry(
        alias="GDP",
        keywords=("gdp", "국내총생산", "경제성장"),
        default_args=SearchArgs(
            table_code="200Y001",
            cycle="Q",
            start_date="2019Q1",
            end_date="2025Q4",
            item_code1="1400",
        ),
        description="실질 국내총생산(분기)",
    ),
    AliasEntry(
        alias="CPI",
        keywords=("cpi", "소비자물가", "물가"),
        default_args=SearchArgs(
            table_code="901Y009",
            cycle="M",
            start_date="202201",
            end_date="202512",
            item_code1="0",
        ),
        description="소비자물가지수(월)",
    ),
    AliasEntry(
        alias="USDKRW",
        keywords=("원달러", "원/달러", "usdkrw", "환율"),
        default_args=SearchArgs(
            table_code="731Y001",
            cycle="D",
            start_date="20240101",
            end_date="20251231",
            item_code1="0000001",
        ),
        description="원/달러 환율(일)",
    ),
    AliasEntry(
        alias="BASE_RATE",
        keywords=("기준금리", "base rate", "policy rate"),
        default_args=SearchArgs(
            table_code="722Y001",
            cycle="M",
            start_date="202201",
            end_date="202512",
            item_code1="0101000",
        ),
        description="한국은행 기준금리(월)",
    ),
    AliasEntry(
        alias="UNEMPLOYMENT",
        keywords=("실업률", "고용", "unemployment"),
        default_args=SearchArgs(
            table_code="901Y027",
            cycle="M",
            start_date="202201",
            end_date="202512",
            item_code1="I61A",
        ),
        description="실업률(월)",
    ),
)
