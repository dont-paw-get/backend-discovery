# ARCHITECTURE — backend-discovery

## 서비스 역할
DPYB(Don't Paw Get Your Book)의 **AI · 탐색(Discovery) 전담 마이크로서비스**.

2026-08-21 방향 전환(`.harness/DECISIONS.md` 참고)으로 역할이 재정의됐다:
자체 벡터DB(pgvector) 기반 카탈로그 읽기 모델은 폐기됐고, 이 서비스는
**Strands Agents SDK 기반 오케스트레이터 및 실시간 웹 검색 도서 추천 / 장르 분류 서비스**로 동작한다.

### 담당 기능
1. **오케스트레이터 에이전트 (Strands Agents SDK)** — 사용자 의도를 파악하여 내 서재 검색(`search_my_library`), 도서 추천 에이전트(`recommend_books`), 사서 상담(`consult_librarian`)으로 라우팅/위임 및 복합 체이닝을 수행한다 (Agent-as-a-Tool 패턴). 도서 추천 시 카드를 본문에 직접 복사하지 않고 서두 안내만 생성하며, 도구 결과 마크다운(`### 📖`, `### 📚`)은 서비스 레이어(`orchestrator_service.py`)의 기존 결합 로직을 통해 전달된다.
2. **내 서재 도서 검색 (`SearchMyLibraryTool`)** — 서재 CRUD 마이크로서비스(`backend-book`)의 `GET /api/v1/library/books` API를 호출하여 로그인 사용자의 서재 도서 목록을 실시간 조회/필터링하고 자연어로 요약한다.
3. **도서 추천 에이전트 (Research Agent)** — 자연어 질의에 웹 검색 도구(Tavily)로 후보 도서 및 실제 쪽수(페이지수)를 찾되, `sanitize_search_results`를 통해 거대 원본 필드(`raw_content`)를 제거하고 400자로 슬라이싱하여 입력 토큰을 최소화한다. 또한 `truncate_books_by_count` 순수 함수를 통해 요청된 `count`개로 결정론적으로 상한을 강제한 정형 마크다운 포맷(`### 📖`, `- **저자**: 저자 (OO쪽)`, `- **추천 이유**:`)으로 응답을 생성한다.
4. **사서 에이전트 연동 (Librarian Tool)** — 별도 사서 마이크로서비스(`backend-librarian`)와 HTTP 통신(`POST /api/v1/chat`)하며, 세션별 활성 사서 ID(`librarian_id`), 사용자 위치 좌표(`latitude`/`longitude`)를 안전하게 주입하고 사서의 `signals`(날씨/무드/장르) 및 `switch_to`(사서 전환 제안)를 오케스트레이션한다. 원격 서비스 장애/미가동 시에는 자체 로컬 fallback 엔진(`evaluate_local_persona_response`)이 인사·의도 게이트·불리언 조건식을 통해 결정론적으로 페르소나 응답과 스위칭 판단을 보정한다.

5. **도서 표준 장르 분류 (`GenreClassifierService`)** — 도서 ISBN 정보를 분석하여 ERD 표준 16개 장르 체계 중 1개로 분류한다 (`POST /api/v1/classify-genre`).
6. **대화 세션 및 메타데이터 관리** — `ChatSessionStore`(Redis)가 멀티턴 대화 히스토리 및 활성 사서/좌표 메타데이터를 sliding TTL로 저장·조회한다.
7. ~~시간대/테마 기반 큐레이션~~, ~~도서 데이터 동기화(벡터 upsert)~~ — 폐기됨.
   상세는 `.harness/DECISIONS.md`, `archive/vector-search-poc/README.md` 참고.

## 기술 스택
| 구분 | 선택 |
| --- | --- |
| 언어/런타임 | Python 3.12 |
| 웹 프레임워크 | FastAPI (async) (포트 8001) |
| 검증/직렬화 | Pydantic V2 (`ConfigDict(from_attributes=True)`) |
| 캐시/세션 | Redis 7 (redis.asyncio) — 대화 세션 및 메타 관리 |
| 에이전트 | Strands Agents SDK (Orchestrator + Agent-as-a-Tool) |
| 웹 검색 도구 | Tavily API (`search_depth="basic"` 고정, `sanitize_search_results` 페이로드 축소) |
| LLM | AWS Bedrock via boto3, Claude Haiku 4.5 글로벌 프로필 (`global.anthropic.claude-haiku-4-5-20251001-v1:0`, `us-east-1`, CLIAR-278, 2026-09-04 — Sonnet 5 대비 레이턴시 개선 목적으로 교체, 단발 호출 실측 평균 약 42% 단축). `max_tokens`만 전달하고 `temperature`/`top_p`/`top_k`는 전달하지 않는다(Sonnet 5에서 확인된 제약을 그대로 유지 — CLIAR-171). |
| 패키지 관리 | uv (`pyproject.toml` + `uv.lock`) |
| 정적 분석 | ruff, mypy |
| 테스트 | pytest, pytest-asyncio, pytest-mock, testcontainers(redis), httpx |
| 관측(트레이싱) | OpenTelemetry SDK 1.44 + OTLP HTTP/protobuf exporter, 자동 계측(FastAPI/redis/botocore/httpx), Strands 자체 agent span 활용. dev는 OTel Collector(`monitoring` ns) → Grafana Tempo |
| 관측(로깅) | 표준 `logging` 기반 stdout JSON (`core/logging.py`), 각 로그에 `trace_id`/`span_id` 주입. Grafana Alloy가 컨테이너 stdout 수집 → Loki |
| 관측(메트릭) | `prometheus-client` 기반 순수 ASGI 미들웨어(`core/metrics.py`)가 `GET /metrics`로 Micrometer 호환 히스토그램(`http_server_requests_seconds_*`) 노출. dev overlay의 ServiceMonitor(`backend-discovery`)로 kube-prometheus-stack이 스크레이핑. OTel MeterProvider는 미도입(pull 방식) |
| 관측(CloudWatch) | CloudWatch 커스텀 메트릭(`DPYB/Discovery/LLM`) + CloudFormation IaC(`docs/observability/cloudwatch-dashboard-stack.yaml`) + 대시보드 위젯 원본(`docs/observability/dashboard.json`) |
| AI 보안(Guardrail) | Amazon Bedrock Guardrails (`apply_guardrail` 인프로세스 게이트), 탈옥/프롬프트인젝션/PII/환각 차단. IaC: CloudFormation 템플릿(`docs/security/guardrail-stack.yaml`) |
| AWS IaC 원칙 | 모든 AWS 리소스(가드레일, 대시보드, IAM 정책 등)는 재현성 보장을 위해 `docs/` 하위 선언형 IaC(CloudFormation / JSON)로 버전 관리 |
| 상세 기능 문서 | `docs/features/` (알라딘 서지 실조회 2단 파이프라인, 4계층 안전 게이트 & Fallback, 16개 표준 장르 분류기) |

**2026-08-21 방향 전환으로 제거된 것**: PostgreSQL, pgvector, SQLAlchemy(async),
asyncpg, Alembic, testcontainers(postgres). RDB로 남는 데이터가 없어 완전히
제거했다 (`.harness/DECISIONS.md` 참고). 폐기된 코드는 `archive/vector-search-poc/`에
보관.

## 시스템 구성
```
클라이언트 ──▶ POST /api/v1/chat (with Bearer Token) ───────┐
            POST /api/v1/classify-genre                     │
                                                            ▼
                        FastAPI (backend-discovery, "오케스트레이터 및 분류기")
                                                            │
         ┌──────────────────┬───────────────────────────────┼──────────────────────────────┬────────────────────────┐
         ▼                  ▼                               ▼                              ▼                        ▼
       Redis      Agent-as-a-Tool (HTTP)          Agent-as-a-Tool (로컬)            Agent-as-a-Tool (HTTP)    Genre Classifier
 (대화 세션 및 메타)  내 서재 검색 도구                 도서 추천 에이전트                  사서 에이전트           (Claude 3 Haiku)
                            │                               │                     (backend-librarian)
                            ▼                               ▼                              │
                 GET /api/v1/library/books            Tavily 웹 검색               (날씨 시그널 / switch_to)
```

## 패키지 구조 / 컨벤션
- 레이어: `domain` → `application` → `infrastructure` / `api`. 의존 방향은 안쪽으로만.
- `domain`은 계산·상태 변경·값 반환까지만 책임진다. 커밋·외부 API 호출은 `application`이 수행.
- 벡터DB/RDB가 없으므로 "AsyncSession 컨텍스트 종료 전 Pydantic 파싱" 규칙은 더 이상
  적용 대상이 없다. 외부 호출(웹 검색, Bedrock, Redis) 결과는 여전히 Pydantic 스키마로
  경계를 넘길 때 직렬화한다.
- 외부 의존성(Bedrock, Redis, 웹 검색 도구, 현재 시각)은 Protocol/DI로 주입해
  결정론적으로 테스트한다.
- 설정값은 `core/config.py`의 pydantic-settings로만 읽고, 접속 정보 기본값을 코드에 두지 않는다.
- 커밋 전 `.pre-commit-config.yaml`(ruff, mypy, 커밋 메시지 `[CLIAR-XX]` 형식 검증)이 자동 실행된다.
  push/merge 승인 정책은 훅 범위가 아니라 `AGENTS.md`의 "Git 작업 정책" 섹션이 규정한다.

### 현재 디렉토리 구조
```
backend-discovery/
├── .harness/            HANDOFF · STATE · ARCHITECTURE · DECISIONS · BACKLOG · PLAN · research/
├── archive/vector-search-poc/   폐기된 pgvector/RAG 코드 보관 (원래 경로 구조 유지)
├── docs/                README.md(종합 색인) · api/ · features/ · observability/ · security/
├── src/discovery/
│   ├── main.py          FastAPI 앱 팩토리, lifespan(Redis만 초기화), /api/v1 라우터 배선,
│   │                     import 시 configure_json_logging() + configure_tracing() 1회 실행,
│   │                     create_app()에서 instrument_fastapi_app(app) 호출
│   ├── core/            config.py(pydantic-settings) · logging.py(stdout JSON 포매터) ·
│   │                     tracing.py(OTel 초기화 + 자동 계측 + 프롬프트 스크러빙 exporter) ·
│   │                     trace_context.py(활성 span → trace_id/span_id 헬퍼) ·
│   │                     observability.py(Strands metrics 구조화 로그)
│   ├── domain/          librarian/(agent.py, post_processor.py) · orchestrator/ · genre/
│   ├── application/     librarian_service.py · orchestrator_service.py · genre_classifier_service.py
│   ├── infrastructure/
│   │   ├── cache/       redis_client.py · chat_session_store.py
│   │   └── search/      book_search_tool.py · result_cache.py · usage_limiter.py
│   └── api/
│       ├── deps.py      get_now, get_chat_session_store, get_genre_classifier_service, get_orchestrator_service ...
│       ├── schemas/     chat.py · genre.py
│       └── v1/routers/  chat.py · genre.py
├── tests/               unit/ · integration/ · conftest.py
├── docker-compose.yml · .env.example · pyproject.toml · uv.lock
```

## 데이터 모델
- **RDB 없음.** `books` 등 벡터DB 기반 읽기 모델은 폐기되어 자체 DB에 도서
  데이터를 복제하지 않는다. 도서 후보는 매 요청 시 웹 검색 도구로 조회한다.
- **Redis 키 구조** (`ChatSessionStore`):
  ```
  1. 세션 히스토리
     키 패턴: chat:session:{session_id}
     타입:    List<string>  (각 원소는 JSON: {"role": "...", "content": "..."})
     TTL:     sliding window — append_turn 호출마다 EXPIRE 갱신 (CHAT_SESSION_TTL_SECONDS)
     길이:    LTRIM으로 최근 CHAT_HISTORY_MAX_TURNS개만 유지 (기본 20)

  2. 세션 메타데이터
     키 패턴: chat:session:{session_id}:meta
     타입:    String (JSON: {"librarian_id": "...", "latitude": 37.5, "longitude": 127.0})
     TTL:     sliding window — update_session_meta 호출마다 EXPIRE 갱신 (CHAT_SESSION_TTL_SECONDS)

  연산:
    APPEND_TURN(session_id, turn)           → RPUSH + LTRIM + EXPIRE
    GET_HISTORY(session_id)                 → LRANGE 0 -1
    GET_SESSION_META(session_id)            → GET
    UPDATE_SESSION_META(session_id, **meta) → SET (ex=TTL)
    CLEAR(session_id)                       → DEL (히스토리 + 메타)
  ```
  `session_id`는 이 스토어가 생성하지 않는다. 호출자가 결정론적으로 발급해 주입한다.

## 관측(Observability) — CLIAR-203 + infra 연동

목적: Trace + 구조화 로그 + Prometheus 메트릭을 infra(dont-paw-get/infra)의
Grafana/Tempo/Loki/Prometheus 및 RCA Agent와 연동. 서비스명 `<SVC>`는 전부
`backend-discovery`로 통일한다(메트릭 `application` 태그 = `OTEL_SERVICE_NAME` =
트레이스 `service.name` = k8s 리소스명). OTel MeterProvider는 여전히 미도입 —
메트릭은 Prometheus pull(`/metrics`) 방식.

- **초기화 위치**: `core/tracing.py`의 `configure_tracing()`(idempotent)이 전역
  `TracerProvider`를 세팅한다. `OTEL_EXPORTER_OTLP_ENDPOINT`(또는 `_TRACES_ENDPOINT`)가
  있을 때만 `BatchSpanProcessor` + OTLP HTTP exporter를 붙인다. 미설정(로컬)이면
  export 없이 정상 기동. 샘플러/서비스명/리소스는 표준 OTel 환경변수로 제어
  (`OTEL_TRACES_SAMPLER`, `OTEL_TRACES_SAMPLER_ARG`, `OTEL_SERVICE_NAME`,
  `OTEL_RESOURCE_ATTRIBUTES`). 전파는 W3C Trace Context(+baggage).
- **자동 계측**: FastAPI(server span, `health/healthz/readyz/livez` 제외 → probe로
  Tempo 오염 방지), redis(GET/SET 등, `db.statement`는 `"SET ? ?"`로 값 마스킹됨),
  botocore(Bedrock InvokeModel 등 — 기본값에서 프롬프트/본문 미수집), httpx(사서·서재
  API 및 Tavily SDK 내부 호출).
- **Strands Agent**: 전역 TracerProvider를 자동 인식해 `invoke_agent` /
  `execute_event_loop_cycle` / `execute_tool <name>` / `chat` span을 스스로 생성한다.
  custom business span은 추가하지 않는다.
- **민감정보 스크러빙**: Strands tracer는 프롬프트·시스템 프롬프트·LLM 응답·도구
  입출력을 span attribute/event에 넣는다. 이를 막기 위해 exporter 앞단에
  `_SanitizingSpanExporter`를 두어 (1) `gen_ai.*` 등 내용 event 제거(`exception` event는
  보존), (2) 민감 attribute 키 제거(`system_prompt`, `gen_ai.input.messages` 등),
  (3) URL query string 제거, (4) 400자 초과 문자열 값 마스킹. 토큰 사용량·모델 ID·
  지연시간 등 metadata는 유지한다.
- **로그 ↔ Trace correlation**: `core/logging.py`의 `JsonLogFormatter`가 매 로그에
  활성 span의 `trace_id`(32 hex)/`span_id`(16 hex)를 JSON 필드로 주입(활성 span
  없으면 null). Loki label로 승격하지 않는다(고카디널리티). `observability.py`의
  구조화 메트릭 로그도 동일 필드를 포함한다.
- **Prometheus 메트릭**: `core/metrics.py`의 `PrometheusMiddleware`(순수 ASGI —
  `BaseHTTPMiddleware`가 아니라서 스트리밍 응답도 마지막 body 청크까지 wall-clock
  계측)가 요청마다 `http_server_requests_seconds` 히스토그램을 기록한다. 이름·구조를
  Spring Micrometer(`_bucket`/`_count`/`_sum`, 라벨 `method`,`uri`,`status`,`outcome`,
  `application`)와 일치시켜 infra의 5xx/p99 알림 규칙이 수정 없이 동작하게 한다.
  버킷은 0.05~60초(LLM 응답 지연 대응). `uri`는 라우트 템플릿(미매칭 시 `"NO_ROUTE"`).
  `/health`·`/api/v1/health`·`/metrics`는 계측 제외. `GET /metrics`가 `generate_latest()`를
  서빙하며 `openapi.yaml`에는 넣지 않는다(ops 엔드포인트, `/health`와 동일 취급).
  스크레이핑은 dev overlay의 ServiceMonitor `backend-discovery`(`port: http`,
  `path: /metrics`, `interval: 30s`) — prod overlay에는 두지 않는다(CRD 부재).
- **probe/스크레이핑 제외**: `_EXCLUDED_URLS = "health,healthz,readyz,livez,metrics"` —
  트레이스 server span 생성을 SDK 단에서 막는다.
- **dev 환경변수**: `k8s/overlays/dev/configmap-patch.yaml` (Secret 아님). traces만
  OTLP export하고 `OTEL_METRICS_EXPORTER=none`/`OTEL_LOGS_EXPORTER=none`.
- **테스트**: `tests/unit/test_tracing.py`, `tests/unit/test_metrics.py`.

## CloudWatch LLM 관측 — CLIAR-276 (선택적 커스텀 메트릭, 기본 OFF)

목적: Bedrock 비용(USD), 토큰 사용량, 캐시 히트율, 및 체감 지연시간(TTFT, End-to-End)을
AWS 네이티브 CloudWatch 커스텀 메트릭으로 수집하여 FinOps 및 모델/캐시 최적화 근거로 활용.

- **격리 원칙**: 기존 Prometheus/Grafana/Loki 관측 스택을 일절 침범하지 않는 완전 독립 경로.
  `Settings.enable_cloudwatch_metrics = False`(기본값)이면 boto3 클라이언트조차 생성하지 않고
  모든 발행 호출이 즉시 no-op으로 종료됨.
- **네임스페이스**: `DPYB/Discovery/LLM` (Prometheus 메트릭과 물리적 분리).
- **발행 메트릭 (Model 단일 차원으로 카디널리티 최소화)**:
  - `RequestLatencyMs`: 요청 전체 소요 시간 (밀리초).
  - `TimeToFirstByteMs`: 스트리밍 응답 시 첫 번째 텍스트 청크 수신까지의 시간 (밀리초, TTFT).
  - `BedrockCostUSD`: 요청 1건의 Bedrock 추정 비용 (USD, `core/pricing.py` 기반).
  - `InputTokens`, `OutputTokens`, `CacheReadTokens`, `CacheWriteTokens`: 토큰 사용량.
  - `SearchCacheHit`, `SearchCacheMiss`: Tavily 검색 결과 캐시(Redis) 히트/미스 카운트.
- **통계 왜곡 방지 가드레일**: `evaluate_safety_gate` 및 `evaluate_input_gate`로 조기 반환된
  요청(LLM 미호출)은 레이턴시 및 비용 발행 대상에서 제외(p50/p90 왜곡 방지).
- **논블로킹 및 Graceful Degradation**: `boto3`의 동기 `put_metric_data`는 `asyncio.to_thread`로
  별도 스레드에서 실행되며, 네트워크 장애 등 발행 실패는 로그만 남기고 조용히 삼킨다.
- **테스트**: `tests/unit/test_cloudwatch_metrics.py`, `tests/unit/test_orchestrator_cloudwatch_metrics.py`.

## 외부 계약
API wire 계약은 이 문서가 아니라 `docs/api/openapi.yaml`이 소유한다.
계약 결정 근거는 `docs/api/decisions/`를 참조한다.
