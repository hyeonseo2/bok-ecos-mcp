# bok-ecos-mcp

MCP server for accessing Bank of Korea ECOS economic statistics. 한국은행 ECOS 경제통계를 조회하는 MCP 서버입니다.

## Features

- MCP tools:
  - `search_tables` — search ECOS table catalog by keyword and return matching table codes/names/cycle info. / 키워드로 ECOS 테이블 카탈로그를 검색해 `table_code`, 이름, 주기 정보를 반환합니다.
  - `list_table_items` — list items (`item_code`, names, units) for a specific table code. / 특정 테이블 코드의 항목 목록(`item_code`, 이름, 단위)을 조회합니다.
  - `get_series` — fetch time-series values with optional filters (`table_code`, `item_code*`, date range, period). / 선택 항목(`table_code`, `item_code*`, 기간, 주기)을 기반으로 시계열 값을 조회합니다.
  - `get_key_statistics` — fetch key national-economy-related statistics list and values. / 주요 경제지표 목록/값을 조회합니다.
  - `resolve_query` — resolve natural-language query (예: "원달러 환율") into search args candidates. / 자연어 질의(예: "원달러 환율")를 검색 파라미터 후보로 해석합니다.
  - `get_server_info` — return transport/runtime metadata, cache TTLs, limits, available tools/resources. / 서버 transport/런타임 정보, 캐시 TTL, 제한치, 사용 가능한 도구/리소스를 반환합니다.
- MCP resources:
  - `ecos://catalog/tables`
  - `ecos://guide/date-formats`
  - `ecos://guide/attribution`
  - `ecos://aliases/common-series`
- Async HTTP client with:
  - endpoint-level TTL cache
  - semaphore concurrency control
  - retry/backoff for retryable failures
  - simple request pacing (rate limiting)
- Strictly normalized JSON envelopes with:
  - `source.attribution`
  - `transformed.fields`
  - warnings and explicit error envelopes
- Commercial safety controls:
  - `commercial_safe_mode`
  - source org allowlist filtering

## Install

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

## Environment Variables

Copy `.env.example` and set values:

```bash
cp .env.example .env
```

Required:

- `BOK_ECOS_API_KEY`

Optional core:

- `BOK_ECOS_BASE_URL` (default: `https://ecos.bok.or.kr/api`)
- `BOK_ECOS_DEFAULT_LANG` (default: `kr`)
- `BOK_ECOS_TIMEOUT_SECONDS`
- `BOK_ECOS_MAX_RETRIES`
- `BOK_ECOS_BACKOFF_BASE_SECONDS`
- `BOK_ECOS_MAX_CONCURRENCY`
- `BOK_ECOS_MIN_INTERVAL_SECONDS`

Optional safety:

- `BOK_ECOS_COMMERCIAL_SAFE_MODE` (`true`/`false`)
- `BOK_ECOS_SOURCE_ORG_ALLOWLIST` (comma-separated)
- `BOK_ECOS_MAX_PAGE_SPAN` (max allowed request span for list endpoints, default: `5000`)
- `BOK_ECOS_MAX_RESOLVE_TOP_K` (max allowed top_k for query resolver, default: `20`)
- `BOK_ECOS_TABLE_FETCH_BATCH_SIZE` (조회 요청 배치 크기, 기본 `500`)

Optional per-endpoint cache TTL:

- `BOK_ECOS_CACHE_TTL_TABLE_LIST`
- `BOK_ECOS_CACHE_TTL_ITEM_LIST`
- `BOK_ECOS_CACHE_TTL_SERIES`
- `BOK_ECOS_CACHE_TTL_KEY_STATS`
- `BOK_ECOS_TRANSPORT` (`stdio`, `streamable-http`; default: `stdio`)
- `BOK_ECOS_HOST` (streamable-http only; default: `127.0.0.1`)
- `BOK_ECOS_PORT` (streamable-http only; default: `8000`)

## Run MCP stdio server

```bash
export BOK_ECOS_API_KEY=your_key
bok-ecos-mcp
```

or:

```bash
python -m bok_ecos_mcp.server
```

## Run MCP streamable-http server

```bash
export BOK_ECOS_API_KEY=your_key
export BOK_ECOS_TRANSPORT=streamable-http
python -m bok_ecos_mcp.server

```

## Example queries

`search_tables`:

```json
{
  "keyword": "GDP",
  "start_count": 1,
  "end_count": 200
}
```

`get_series`:

```json
{
  "table_code": "200Y001",
  "item_code1": "1400",
  "cycle": "Q",
  "start_date": "2022Q1",
  "end_date": "2024Q4"
}
```

`resolve_query`:

```json
{
  "query": "원달러 환율 일간 최근 90일",
  "top_k": 5
}
```

## Development

Run lint/format and tests:

```bash
ruff check .
ruff format .
pytest
```

