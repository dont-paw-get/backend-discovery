# ARCHITECTURE — backend-discovery

## 서비스 역할
DPYB(Don't Paw Get Your Book)의 **AI · 탐색(Discovery) 전담 마이크로서비스**.

2026-08-21 방향 전환(`.harness/DECISIONS.md` 참고)으로 역할이 재정의됐다:
자체 벡터DB(pgvector) 기반 카탈로그 읽기 모델은 폐기됐고, 이 서비스는
**Strands Agents SDK 기반 오케스트레이터 및 실시간 웹 검색 도서 추천 / 장르 분류 서비스**로 동작한다.

### 담당 기능
1. **오케스트레이터 에이전트 (Strands Agents SDK)** — 사용자 의도를 파악하여 도서 추천 에이전트(로컬 도구) 또는 사서 에이전트(HTTP 원격 도구)로 라우팅/위임한다 (Agent-as-a-Tool 패턴).
2. **도서 추천 에이전트 (Research Agent)** — 자연어 질의에 웹 검색 도구(Tavily)로 후보 도서를 찾고, 정형화된 마크다운 템플릿으로 추천 답변을 생성한다.
3. **사서 에이전트 연동 (Librarian Tool)** — 별도 사서 서비스(`backend-librarian`)와 HTTP 통신하며, 서비스 미가동 시 graceful 스텁 응답을 제공한다.
4. **도서 표준 장르 분류 (`GenreClassifierService`)** — 도서 제목, 저자, 원본 카테고리(알라딘/OCR 등) 정보를 분석하여 ERD 표준 16개 장르 체계 중 1개로 분류한다 (`POST /api/v1/classify-genre`).
5. **대화 세션 관리** — `ChatSessionStore`(Redis)가 멀티턴 대화 히스토리를 sliding TTL로 저장·조회한다.
6. ~~시간대/테마 기반 큐레이션~~, ~~도서 데이터 동기화(벡터 upsert)~~ — 폐기됨.
   상세는 `.harness/DECISIONS.md`, `archive/vector-search-poc/README.md` 참고.

## 기술 스택
| 구분 | 선택 |
| --- | --- |
| 언어/런타임 | Python 3.12 |
| 웹 프레임워크 | FastAPI (async) |
| 검증/직렬화 | Pydantic V2 (`ConfigDict(from_attributes=True)`) |
| 캐시/세션 | Redis 7 (redis.asyncio) — 대화 세션 관리 |
| 에이전트 | Strands Agents SDK (Orchestrator + Agent-as-a-Tool) |
| 웹 검색 도구 | Tavily API (`search_depth="basic"` 고정, 무료 티어 월 1,000 크레딧 비용 방어) |
| LLM | AWS Bedrock via boto3, Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`) |
| 패키지 관리 | uv (`pyproject.toml` + `uv.lock`) |
| 정적 분석 | ruff, mypy |
| 테스트 | pytest, pytest-asyncio, pytest-mock, testcontainers(redis), httpx |

**2026-08-21 방향 전환으로 제거된 것**: PostgreSQL, pgvector, SQLAlchemy(async),
asyncpg, Alembic, testcontainers(postgres). RDB로 남는 데이터가 없어 완전히
제거했다 (`.harness/DECISIONS.md` 참고). 폐기된 코드는 `archive/vector-search-poc/`에
보관.

## 시스템 구성
```
클라이언트 ──▶ POST /api/v1/chat ────────┐
            POST /api/v1/classify-genre  │
                                         ▼
                     FastAPI (backend-discovery, "오케스트레이터 및 분류기")
                                         │
        ┌────────────────────────────────┼──────────────────────────────┬────────────────────────┐
        ▼                                ▼                              ▼                        ▼
    Redis                     Agent-as-a-Tool (로컬)            Agent-as-a-Tool (HTTP)    Genre Classifier
(대화 세션 관리)               도서 추천 에이전트                  사서 에이전트 스텁       (Claude 3 Haiku)
                                         │                     (backend-librarian)
                                         ▼
                                 Tavily 웹 검색
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
├── docs/api/            openapi.yaml · README.md · decisions/
├── src/discovery/
│   ├── main.py          FastAPI 앱 팩토리, lifespan(Redis만 초기화), /api/v1 라우터 배선
│   ├── core/            config.py(pydantic-settings)
│   ├── domain/          librarian/ · orchestrator/ · genre/
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
  키 패턴: chat:session:{session_id}
  타입:    List<string>  (각 원소는 JSON: {"role": "...", "content": "..."})
  TTL:     sliding window — append_turn 호출마다 EXPIRE 갱신
           (CHAT_SESSION_TTL_SECONDS, 기본 3600s)
  길이 제한: LTRIM으로 최근 CHAT_HISTORY_MAX_TURNS개만 유지 (기본 20)

  연산:
    APPEND_TURN(session_id, turn) → RPUSH + LTRIM + EXPIRE
    GET_HISTORY(session_id)       → LRANGE 0 -1
    CLEAR(session_id)             → DEL
  ```
  `session_id`는 이 스토어가 생성하지 않는다. 호출자가 결정론적으로 발급해 주입한다.

## 외부 계약
API wire 계약은 이 문서가 아니라 `docs/api/openapi.yaml`이 소유한다.
계약 결정 근거는 `docs/api/decisions/`를 참조한다.
