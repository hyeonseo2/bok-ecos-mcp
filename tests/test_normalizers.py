from __future__ import annotations

import pytest

from bok_ecos_mcp.errors import EcosValidationError
from bok_ecos_mcp.normalizers import parse_numeric, validate_date_range


def test_parse_numeric_success() -> None:
    assert parse_numeric("1,234.5") == 1234.5
    assert parse_numeric("  -10 ") == -10.0
    assert parse_numeric("") is None


def test_parse_numeric_non_numeric() -> None:
    assert parse_numeric("N/A") is None


def test_validate_date_range_quarter_normalizes() -> None:
    cycle, start, end = validate_date_range("q", "20241", "2024Q4")
    assert cycle == "Q"
    assert start == "2024Q1"
    assert end == "2024Q4"


def test_validate_date_range_daily_invalid() -> None:
    with pytest.raises(EcosValidationError):
        validate_date_range("D", "20240230", "20240301")


def test_validate_date_range_reversed() -> None:
    with pytest.raises(EcosValidationError):
        validate_date_range("M", "202412", "202401")
