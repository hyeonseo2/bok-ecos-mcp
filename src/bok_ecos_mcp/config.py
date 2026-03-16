"""Configuration loading from environment variables."""

from __future__ import annotations

from dataclasses import dataclass
import os

from .errors import ConfigError


def _env_bool(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    normalized = raw_value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ConfigError(f"Invalid boolean value for {name}: {raw_value}")


def _env_int(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = int(raw_value)
    except ValueError as exc:
        raise ConfigError(f"Invalid integer value for {name}: {raw_value}") from exc
    if parsed < 0:
        raise ConfigError(f"{name} must be >= 0")
    return parsed


def _env_positive_int(name: str, default: int) -> int:
    parsed = _env_int(name, default)
    if parsed < 1:
        raise ConfigError(f"{name} must be >= 1")
    return parsed


def _env_float(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        parsed = float(raw_value)
    except ValueError as exc:
        raise ConfigError(f"Invalid float value for {name}: {raw_value}") from exc
    if parsed < 0:
        raise ConfigError(f"{name} must be >= 0")
    return parsed


def _env_allowlist(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    values = tuple(item.strip() for item in raw_value.split(",") if item.strip())
    if not values:
        raise ConfigError(f"{name} cannot be empty when provided")
    return values


@dataclass(frozen=True, slots=True)
class Settings:
    """Runtime settings for the MCP server and ECOS client."""

    ecos_api_key: str
    ecos_base_url: str = "https://ecos.bok.or.kr/api"
    default_lang: str = "kr"
    timeout_seconds: float = 10.0
    max_retries: int = 3
    backoff_base_seconds: float = 0.4
    max_concurrency: int = 4
    min_interval_seconds: float = 0.2
    commercial_safe_mode: bool = True
    source_org_allowlist: tuple[str, ...] = ("한국은행",)
    cache_ttl_table_list: int = 3600
    cache_ttl_item_list: int = 3600
    cache_ttl_series: int = 300
    cache_ttl_key_stats: int = 600
    max_page_span: int = 5000
    max_resolve_top_k: int = 20
    table_fetch_batch_size: int = 500

    @classmethod
    def from_env(cls, require_api_key: bool = True) -> "Settings":
        """Build Settings from environment variables."""
        api_key = os.getenv("BOK_ECOS_API_KEY", "").strip()
        if require_api_key and not api_key:
            raise ConfigError("BOK_ECOS_API_KEY is required")
        return cls(
            ecos_api_key=api_key,
            ecos_base_url=os.getenv("BOK_ECOS_BASE_URL", "https://ecos.bok.or.kr/api").rstrip("/"),
            default_lang=os.getenv("BOK_ECOS_DEFAULT_LANG", "kr"),
            timeout_seconds=_env_float("BOK_ECOS_TIMEOUT_SECONDS", 10.0),
            max_retries=_env_int("BOK_ECOS_MAX_RETRIES", 3),
            backoff_base_seconds=_env_float("BOK_ECOS_BACKOFF_BASE_SECONDS", 0.4),
            max_concurrency=max(1, _env_int("BOK_ECOS_MAX_CONCURRENCY", 4)),
            min_interval_seconds=_env_float("BOK_ECOS_MIN_INTERVAL_SECONDS", 0.2),
            commercial_safe_mode=_env_bool("BOK_ECOS_COMMERCIAL_SAFE_MODE", True),
            source_org_allowlist=_env_allowlist(
                "BOK_ECOS_SOURCE_ORG_ALLOWLIST",
                ("한국은행",),
            ),
            cache_ttl_table_list=_env_int("BOK_ECOS_CACHE_TTL_TABLE_LIST", 3600),
            cache_ttl_item_list=_env_int("BOK_ECOS_CACHE_TTL_ITEM_LIST", 3600),
            cache_ttl_series=_env_int("BOK_ECOS_CACHE_TTL_SERIES", 300),
            cache_ttl_key_stats=_env_int("BOK_ECOS_CACHE_TTL_KEY_STATS", 600),
            max_page_span=_env_int("BOK_ECOS_MAX_PAGE_SPAN", 5000),
            max_resolve_top_k=_env_int("BOK_ECOS_MAX_RESOLVE_TOP_K", 20),
            table_fetch_batch_size=_env_positive_int("BOK_ECOS_TABLE_FETCH_BATCH_SIZE", 500),
        )
