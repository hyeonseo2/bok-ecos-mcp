# bok-ecos-mcp 한국은행 경제통계시스템(ECOS) 조회 MCP

**MCP server for accessing economic data from the Bank of Korea ECOS (Economic Statistics System).**    
**한국은행 경제통계시스템(ECOS) 데이터를 조회하는 MCP 서버입니다.**
- **한국어 문서:** [README_KO.md](./README_KO.md)

This project exposes the **Bank of Korea ECOS OpenAPI** as **MCP tools**, allowing AI agents and LLM applications to discover statistical tables and retrieve Korean economic time-series data programmatically.

---

# Overview

**ECOS (Economic Statistics System)** is the official economic statistics platform operated by the **Bank of Korea**.

While ECOS provides a public OpenAPI, accessing the data typically requires knowledge of:

* statistical table codes
* item codes
* time cycles (daily / monthly / quarterly)
* ECOS-specific date formats

This MCP server simplifies the process by exposing structured tools that allow agents and applications to:

* search statistical tables
* explore table item codes
* retrieve economic time-series data
* resolve user queries into ECOS search parameters

The server can be used with **AI agents, LLM applications, or developer tools that support the Model Context Protocol (MCP).**

---

# Features

## MCP Tools

| Tool                 | Description                                                                       |
| -------------------- | --------------------------------------------------------------------------------- |
| `search_tables`      | Search ECOS table catalog by keyword and return matching table codes and metadata |
| `list_table_items`   | List item codes, names, and units for a specific table                            |
| `get_series`         | Retrieve time-series data using table/item codes                                  |
| `get_key_statistics` | Retrieve key national economic indicators                                         |
| `resolve_query`      | Resolve natural-language queries into ECOS search parameters                      |
| `get_server_info`    | Return server metadata and available tools/resources                              |

---

## MCP Resources

| Resource                       | Description                       |
| ------------------------------ | --------------------------------- |
| `ecos://catalog/tables`        | ECOS table catalog                |
| `ecos://guide/date-formats`    | ECOS date format guide            |
| `ecos://guide/attribution`     | Data attribution guidelines       |
| `ecos://aliases/common-series` | Common economic indicator aliases |

---

## Runtime Capabilities

* asynchronous HTTP client
* endpoint-level TTL cache
* semaphore-based concurrency control
* retry + exponential backoff
* request pacing / rate limiting
* normalized JSON response envelopes
* structured warnings and error responses

---

## Safety Controls

To support safe usage of ECOS data in production environments:

* `commercial_safe_mode`
* source organization allowlist filtering

These controls help ensure compliance when using ECOS data in commercial contexts.

---

# Installation

Create a virtual environment and install the package.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
```

---

# Environment Variables

Copy the example environment file.

```bash
cp .env.example .env
```

### Required

```
BOK_ECOS_API_KEY
```

---

### Core Configuration

```
BOK_ECOS_BASE_URL=https://ecos.bok.or.kr/api
BOK_ECOS_DEFAULT_LANG=kr
BOK_ECOS_TIMEOUT_SECONDS
BOK_ECOS_MAX_RETRIES
BOK_ECOS_BACKOFF_BASE_SECONDS
BOK_ECOS_MAX_CONCURRENCY
BOK_ECOS_MIN_INTERVAL_SECONDS
```

---

### Safety Controls

```
BOK_ECOS_COMMERCIAL_SAFE_MODE=true|false
BOK_ECOS_SOURCE_ORG_ALLOWLIST
BOK_ECOS_MAX_PAGE_SPAN
BOK_ECOS_MAX_RESOLVE_TOP_K
BOK_ECOS_TABLE_FETCH_BATCH_SIZE
```

---

### Cache Configuration

```
BOK_ECOS_CACHE_TTL_TABLE_LIST
BOK_ECOS_CACHE_TTL_ITEM_LIST
BOK_ECOS_CACHE_TTL_SERIES
BOK_ECOS_CACHE_TTL_KEY_STATS
```

---

### Transport Settings

```
BOK_ECOS_TRANSPORT=stdio|streamable-http
BOK_ECOS_HOST
BOK_ECOS_PORT
```

Default transport is **stdio**.

---

# Running the MCP Server

## stdio mode (recommended)

```bash
export BOK_ECOS_API_KEY=your_key
bok-ecos-mcp
```

or

```bash
python -m bok_ecos_mcp.server
```

---

## streamable-http mode

```bash
export BOK_ECOS_API_KEY=your_key
export BOK_ECOS_TRANSPORT=streamable-http

python -m bok_ecos_mcp.server
```

---

# Example Queries

## search_tables

```json
{
  "keyword": "GDP",
  "start_count": 1,
  "end_count": 200
}
```

---

## get_series

```json
{
  "table_code": "200Y001",
  "item_code1": "1400",
  "cycle": "Q",
  "start_date": "2022Q1",
  "end_date": "2024Q4"
}
```

---

## resolve_query

```json
{
  "query": "원달러 환율 일간 최근 90일",
  "top_k": 5
}
```

---

# Development

Run linting, formatting, and tests.

```bash
ruff check .
ruff format .
pytest
```

---

# Data Source

This project uses the **Bank of Korea ECOS OpenAPI**.

[https://ecos.bok.or.kr/](https://ecos.bok.or.kr/)

All statistics are provided by the **Bank of Korea Economic Statistics System (ECOS)**.
When using ECOS data, please follow the attribution guidelines provided by the Bank of Korea.

---

# License

MIT License


