# bok-ecos-mcp 한국은행 경제통계시스템(ECOS) 조회 MCP

**한국은행 경제통계시스템(ECOS) 데이터를 조회하기 위한 MCP 서버입니다.**

- **English documentation:** [README.md](./README.md)

이 프로젝트는 **한국은행 ECOS OpenAPI**를 **MCP 도구(MCP tools)** 형태로 제공하여  
AI 에이전트 및 LLM 애플리케이션이 한국 경제 통계 테이블을 탐색하고 경제 시계열 데이터를  
프로그램 방식으로 조회할 수 있도록 합니다.

---

# 개요 (Overview)

**ECOS (Economic Statistics System)** 는 **한국은행(Bank of Korea)** 이 운영하는 공식 경제통계 플랫폼입니다.

ECOS는 공개 OpenAPI를 제공하지만 실제 데이터를 조회하려면 다음과 같은 정보를 이해해야 합니다.

* 통계 테이블 코드 (statistical table code)
* 항목 코드 (item code)
* 시계열 주기 (일/월/분기 등)
* ECOS 전용 날짜 포맷

이 MCP 서버는 이러한 과정을 단순화하기 위해 다음과 같은 기능을 제공합니다.

* 통계 테이블 검색
* 테이블 항목 코드 탐색
* 경제 시계열 데이터 조회
* 자연어 질의를 ECOS 검색 파라미터로 변환

이 서버는 **Model Context Protocol (MCP)** 을 지원하는 다음 환경에서 사용할 수 있습니다.

* AI 에이전트
* LLM 애플리케이션
* MCP를 지원하는 개발 도구

---

# 주요 기능 (Features)

## MCP Tools

| Tool | 설명 |
|-----|------|
| `search_tables` | 키워드를 기반으로 ECOS 통계 테이블을 검색하고 테이블 코드 및 메타데이터를 반환합니다 |
| `list_table_items` | 특정 통계 테이블의 항목 코드, 이름, 단위를 조회합니다 |
| `get_series` | 테이블/항목 코드를 이용해 시계열 데이터를 조회합니다 |
| `get_key_statistics` | 주요 국가 경제 지표를 조회합니다 |
| `resolve_query` | 자연어 질의를 ECOS 검색 파라미터로 변환합니다 |
| `get_server_info` | 서버 메타데이터 및 사용 가능한 MCP 도구/리소스를 반환합니다 |

---

## MCP Resources

| Resource | 설명 |
|--------|------|
| `ecos://catalog/tables` | ECOS 통계 테이블 카탈로그 |
| `ecos://guide/date-formats` | ECOS 날짜 포맷 가이드 |
| `ecos://guide/attribution` | 데이터 출처 표시 가이드 |
| `ecos://aliases/common-series` | 자주 사용되는 경제 지표 별칭 |

---

## 런타임 기능 (Runtime Capabilities)

* 비동기 HTTP 클라이언트
* endpoint 단위 TTL 캐시
* semaphore 기반 동시성 제어
* retry 및 exponential backoff
* 요청 속도 제한 (rate limiting)
* 정규화된 JSON 응답 구조
* 구조화된 경고 및 오류 응답

---

## 안전 설정 (Safety Controls)

프로덕션 환경에서 ECOS 데이터를 안전하게 사용하기 위한 설정입니다.

* `commercial_safe_mode`
* source organization allowlist 필터링

이 설정들은 상업적 환경에서 ECOS 데이터를 사용할 때  
데이터 출처 및 정책 준수를 지원합니다.

---

# 설치 (Installation)

가상환경을 생성하고 패키지를 설치합니다.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .[dev]
````

---

# 환경 변수 (Environment Variables)

예시 환경 파일을 복사합니다.

```bash
cp .env.example .env
```

### 필수 설정

```
BOK_ECOS_API_KEY
```

---

### 기본 설정

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

### 안전 설정

```
BOK_ECOS_COMMERCIAL_SAFE_MODE=true|false
BOK_ECOS_SOURCE_ORG_ALLOWLIST
BOK_ECOS_MAX_PAGE_SPAN
BOK_ECOS_MAX_RESOLVE_TOP_K
BOK_ECOS_TABLE_FETCH_BATCH_SIZE
```

---

### 캐시 설정

```
BOK_ECOS_CACHE_TTL_TABLE_LIST
BOK_ECOS_CACHE_TTL_ITEM_LIST
BOK_ECOS_CACHE_TTL_SERIES
BOK_ECOS_CACHE_TTL_KEY_STATS
```

---

### Transport 설정

```
BOK_ECOS_TRANSPORT=stdio|streamable-http
BOK_ECOS_HOST
BOK_ECOS_PORT
```

기본 transport는 **stdio** 입니다.

---

# MCP 서버 실행

## stdio 모드 (권장)

```bash
export BOK_ECOS_API_KEY=your_key
bok-ecos-mcp
```

또는

```bash
python -m bok_ecos_mcp.server
```

---

## streamable-http 모드

```bash
export BOK_ECOS_API_KEY=your_key
export BOK_ECOS_TRANSPORT=streamable-http

python -m bok_ecos_mcp.server
```

---

# 사용 예시 (Example Queries)

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

# 개발 (Development)

코드 스타일 검사 및 테스트 실행

```bash
ruff check .
ruff format .
pytest
```

---

# 데이터 출처 (Data Source)

이 프로젝트는 **한국은행 ECOS OpenAPI**를 사용합니다.

[https://ecos.bok.or.kr/](https://ecos.bok.or.kr/)

모든 통계 데이터는
**한국은행 경제통계시스템(ECOS)** 에서 제공됩니다.

ECOS 데이터를 사용할 때는 한국은행의 **출처 표시 가이드라인**을 준수해야 합니다.

---

# 라이선스 (License)

MIT License
