"""Async ECOS API client with retry/backoff, cache, and simple rate limiting."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any
from urllib.parse import quote

import httpx

from .cache import AsyncTTLCache, SimpleRateLimiter
from .config import Settings
from .errors import EcosAPIError, EcosNetworkError, EcosRateLimitError
from .models import SearchArgs

logger = logging.getLogger(__name__)

_RETRYABLE_STATUS = {429, 500, 502, 503, 504}


class EcosClient:
    """Typed async client for Bank of Korea ECOS Open API."""

    def __init__(self, settings: Settings, http_client: httpx.AsyncClient | None = None) -> None:
        self._settings = settings
        self._cache: AsyncTTLCache[list[dict[str, Any]]] = AsyncTTLCache()
        self._rate_limiter = SimpleRateLimiter(settings.min_interval_seconds)
        self._semaphore = asyncio.Semaphore(settings.max_concurrency)
        self._http_client = http_client or httpx.AsyncClient(timeout=settings.timeout_seconds)
        self._owns_http_client = http_client is None

    async def close(self) -> None:
        if self._owns_http_client:
            await self._http_client.aclose()

    def _build_url(
        self,
        service: str,
        *,
        start: int,
        end: int,
        lang: str,
        segments: tuple[str, ...] = (),
    ) -> str:
        base = self._settings.ecos_base_url.rstrip("/")
        encoded_segments = "/".join(quote(segment, safe="") for segment in segments)
        if encoded_segments:
            return (
                f"{base}/{service}/{self._settings.ecos_api_key}/json/{lang}/{start}/{end}/"
                f"{encoded_segments}"
            )
        return f"{base}/{service}/{self._settings.ecos_api_key}/json/{lang}/{start}/{end}"

    async def statistic_table_list(
        self,
        *,
        start: int = 1,
        end: int = 1000,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._fetch_rows(
            service="StatisticTableList",
            start=start,
            end=end,
            lang=lang,
            segments=(),
            cache_ttl=self._settings.cache_ttl_table_list,
        )

    async def statistic_item_list(
        self,
        *,
        table_code: str,
        start: int = 1,
        end: int = 1000,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._fetch_rows(
            service="StatisticItemList",
            start=start,
            end=end,
            lang=lang,
            segments=(table_code,),
            cache_ttl=self._settings.cache_ttl_item_list,
        )

    async def statistic_search(
        self,
        *,
        args: SearchArgs,
        start: int = 1,
        end: int = 1000,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        segments = (
            args.table_code,
            args.cycle,
            args.start_date,
            args.end_date,
            args.item_code1,
            args.item_code2,
            args.item_code3,
            args.org_code,
        )
        return await self._fetch_rows(
            service="StatisticSearch",
            start=start,
            end=end,
            lang=lang,
            segments=segments,
            cache_ttl=self._settings.cache_ttl_series,
        )

    async def key_statistic_list(
        self,
        *,
        start: int = 1,
        end: int = 100,
        lang: str | None = None,
    ) -> list[dict[str, Any]]:
        return await self._fetch_rows(
            service="KeyStatisticList",
            start=start,
            end=end,
            lang=lang,
            segments=(),
            cache_ttl=self._settings.cache_ttl_key_stats,
        )

    async def _fetch_rows(
        self,
        *,
        service: str,
        start: int,
        end: int,
        lang: str | None,
        segments: tuple[str, ...],
        cache_ttl: int,
    ) -> list[dict[str, Any]]:
        effective_lang = lang or self._settings.default_lang
        cache_key = json.dumps(
            {
                "service": service,
                "start": start,
                "end": end,
                "lang": effective_lang,
                "segments": segments,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        cached = await self._cache.get(cache_key)
        if cached is not None:
            return cached

        url = self._build_url(
            service,
            start=start,
            end=end,
            lang=effective_lang,
            segments=segments,
        )
        rows = await self._request_rows(url=url, service=service)
        await self._cache.set(cache_key, rows, cache_ttl)
        return rows

    async def _request_rows(self, *, url: str, service: str) -> list[dict[str, Any]]:
        response: httpx.Response | None = None

        for attempt in range(self._settings.max_retries + 1):
            await self._rate_limiter.wait_turn()
            async with self._semaphore:
                try:
                    response = await self._http_client.get(url)
                except httpx.TimeoutException as exc:
                    if attempt >= self._settings.max_retries:
                        raise EcosNetworkError(f"Timeout while calling ECOS: {url}") from exc
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue
                except httpx.NetworkError as exc:
                    if attempt >= self._settings.max_retries:
                        raise EcosNetworkError(f"Network error while calling ECOS: {url}") from exc
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue

            if response.status_code in _RETRYABLE_STATUS:
                if attempt < self._settings.max_retries:
                    await asyncio.sleep(self._backoff_delay(attempt))
                    continue

                if response.status_code == 429:
                    raise EcosRateLimitError(f"ECOS rate limit reached after retries: {url}")
                raise EcosAPIError(
                    f"ECOS HTTP error {response.status_code} for service {service} after retries"
                )

            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise EcosAPIError(
                    f"ECOS HTTP error {response.status_code} for service {service}"
                ) from exc
            break

        if response is None:
            raise EcosNetworkError("No HTTP response produced")

        try:
            payload = response.json()
        except ValueError as exc:
            raise EcosAPIError(f"Invalid JSON from ECOS service {service}") from exc

        if not isinstance(payload, dict):
            raise EcosAPIError(f"Unexpected ECOS payload shape for {service}")

        service_data = payload.get(service)
        if isinstance(service_data, dict):
            result = service_data.get("RESULT")
            if isinstance(result, dict):
                code = str(result.get("CODE", ""))
                if code and code != "INFO-000":
                    message = str(result.get("MESSAGE", "Unknown ECOS API error"))
                    raise EcosAPIError(f"ECOS API error {code}: {message}")
            row = service_data.get("row", [])
            if isinstance(row, list):
                typed_rows = [item for item in row if isinstance(item, dict)]
                return typed_rows
            return []

        result = payload.get("RESULT")
        if isinstance(result, dict):
            code = str(result.get("CODE", ""))
            message = str(result.get("MESSAGE", "Unknown ECOS API error"))
            raise EcosAPIError(f"ECOS API error {code}: {message}")

        raise EcosAPIError(f"Missing '{service}' block in ECOS response")

    def _backoff_delay(self, attempt: int) -> float:
        return self._settings.backoff_base_seconds * (2**attempt)
