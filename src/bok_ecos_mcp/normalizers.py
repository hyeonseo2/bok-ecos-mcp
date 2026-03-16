"""Normalization helpers for ECOS tool responses."""

from __future__ import annotations

from datetime import datetime
import re
from typing import Any

from .errors import EcosValidationError
from .models import Envelope, SourceMetadata

_CYCLE_RE = {
    "A": re.compile(r"^\d{4}$"),
    "S": re.compile(r"^\d{4}(1|2)$"),
    "Q": re.compile(r"^\d{4}Q[1-4]$", re.IGNORECASE),
    "M": re.compile(r"^\d{6}$"),
    "SM": re.compile(r"^\d{6}(1|2)$"),
    "D": re.compile(r"^\d{8}$"),
}


def parse_numeric(value: str | None) -> float | None:
    """Parse number-like strings into float when possible."""
    if value is None:
        return None
    stripped = value.strip()
    if stripped == "":
        return None
    normalized = stripped.replace(",", "")
    try:
        return float(normalized)
    except ValueError:
        return None


def normalize_cycle(cycle: str) -> str:
    upper = cycle.strip().upper()
    if upper not in _CYCLE_RE:
        raise EcosValidationError(f"Unsupported cycle: {cycle}")
    return upper


def normalize_date_by_cycle(cycle: str, value: str) -> str:
    """Validate and normalize a date string for ECOS cycle formats."""
    normalized_cycle = normalize_cycle(cycle)
    normalized_value = value.strip().upper()

    if normalized_cycle == "S" and re.match(r"^\d{4}H[12]$", normalized_value):
        normalized_value = f"{normalized_value[:4]}{normalized_value[-1]}"
    if normalized_cycle == "Q" and re.match(r"^\d{4}[1-4]$", normalized_value):
        normalized_value = f"{normalized_value[:4]}Q{normalized_value[-1]}"

    pattern = _CYCLE_RE[normalized_cycle]
    if pattern.match(normalized_value) is None:
        raise EcosValidationError(
            f"Invalid date '{value}' for cycle {normalized_cycle}."
        )

    if normalized_cycle == "M":
        month = int(normalized_value[4:6])
        if month < 1 or month > 12:
            raise EcosValidationError(f"Invalid month in date: {value}")
    elif normalized_cycle == "SM":
        month = int(normalized_value[4:6])
        if month < 1 or month > 12:
            raise EcosValidationError(f"Invalid month in date: {value}")
    elif normalized_cycle == "D":
        try:
            datetime.strptime(normalized_value, "%Y%m%d")
        except ValueError as exc:
            raise EcosValidationError(f"Invalid calendar date: {value}") from exc

    return normalized_value


def _date_order_key(cycle: str, value: str) -> tuple[int, int, int]:
    if cycle == "A":
        return (int(value), 0, 0)
    if cycle == "S":
        return (int(value[:4]), int(value[4]), 0)
    if cycle == "Q":
        return (int(value[:4]), int(value[-1]), 0)
    if cycle == "M":
        return (int(value[:4]), int(value[4:6]), 0)
    if cycle == "SM":
        return (int(value[:4]), int(value[4:6]), int(value[6]))
    if cycle == "D":
        return (int(value[:4]), int(value[4:6]), int(value[6:8]))
    raise EcosValidationError(f"Unsupported cycle: {cycle}")


def validate_date_range(cycle: str, start_date: str, end_date: str) -> tuple[str, str, str]:
    normalized_cycle = normalize_cycle(cycle)
    normalized_start = normalize_date_by_cycle(normalized_cycle, start_date)
    normalized_end = normalize_date_by_cycle(normalized_cycle, end_date)
    if _date_order_key(normalized_cycle, normalized_start) > _date_order_key(
        normalized_cycle,
        normalized_end,
    ):
        raise EcosValidationError("start_date must be <= end_date")
    return normalized_cycle, normalized_start, normalized_end


def make_envelope(
    *,
    ok: bool,
    request: dict[str, Any],
    data: dict[str, Any],
    transformed_fields: list[str],
    warnings: list[str] | None = None,
    organization: str = "한국은행",
) -> dict[str, Any]:
    envelope = Envelope(
        ok=ok,
        request=request,
        data=data,
        warnings=warnings or [],
        transformed_fields=transformed_fields,
        source=SourceMetadata(organization=organization),
    )
    return envelope.to_dict()


def make_error_envelope(
    *,
    request: dict[str, Any],
    error_code: str,
    message: str,
    warnings: list[str] | None = None,
) -> dict[str, Any]:
    return make_envelope(
        ok=False,
        request=request,
        data={"error": {"code": error_code, "message": message}},
        transformed_fields=["error"],
        warnings=warnings,
    )


def _normalize_text(value: Any) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped if stripped else None
    return None


def filter_rows_by_allowlist(
    rows: list[dict[str, Any]],
    allowlist: tuple[str, ...],
    enabled: bool,
) -> tuple[list[dict[str, Any]], list[str]]:
    if not enabled:
        return rows, []

    filtered: list[dict[str, Any]] = []
    skipped = 0
    allowlist_set = set(allowlist)
    for row in rows:
        org_name = _normalize_text(row.get("ORG_NAME"))
        if org_name is None or org_name in allowlist_set:
            filtered.append(row)
        else:
            skipped += 1

    warnings: list[str] = []
    if skipped > 0:
        warnings.append(
            f"commercial_safe_mode filtered {skipped} rows due to source org allowlist"
        )
    return filtered, warnings


def normalize_table_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "table_code": _normalize_text(row.get("STAT_CODE")),
                "table_name": _normalize_text(row.get("STAT_NAME")),
                "cycle": _normalize_text(row.get("CYCLE")),
                "org_name": _normalize_text(row.get("ORG_NAME")),
                "search_keyword": _normalize_text(row.get("SRCH_YN")),
                "raw": row,
            }
        )
    return normalized


def normalize_item_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append(
            {
                "table_code": _normalize_text(row.get("STAT_CODE")),
                "item_name": _normalize_text(row.get("ITEM_NAME")),
                "item_code": _normalize_text(row.get("ITEM_CODE")),
                "unit_name": _normalize_text(row.get("UNIT_NAME")),
                "cycle": _normalize_text(row.get("CYCLE")),
                "raw": row,
            }
        )
    return normalized


def normalize_series_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        value_raw = _normalize_text(row.get("DATA_VALUE"))
        normalized.append(
            {
                "table_code": _normalize_text(row.get("STAT_CODE")),
                "time": _normalize_text(row.get("TIME")),
                "item_code1": _normalize_text(row.get("ITEM_CODE1")),
                "item_code2": _normalize_text(row.get("ITEM_CODE2")),
                "item_code3": _normalize_text(row.get("ITEM_CODE3")),
                "unit_name": _normalize_text(row.get("UNIT_NAME")),
                "org_name": _normalize_text(row.get("ORG_NAME")),
                "value_raw": value_raw,
                "value": parse_numeric(value_raw),
                "raw": row,
            }
        )
    return normalized


def normalize_key_stat_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        value_raw = _normalize_text(row.get("DATA_VALUE"))
        normalized.append(
            {
                "class_name": _normalize_text(row.get("CLASS_NAME")),
                "key_stat_name": _normalize_text(row.get("KEYSTAT_NAME")),
                "unit_name": _normalize_text(row.get("UNIT_NAME")),
                "cycle": _normalize_text(row.get("CYCLE")),
                "time": _normalize_text(row.get("TIME")),
                "value_raw": value_raw,
                "value": parse_numeric(value_raw),
                "raw": row,
            }
        )
    return normalized
