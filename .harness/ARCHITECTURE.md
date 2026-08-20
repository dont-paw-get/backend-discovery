# ARCHITECTURE — backend-discovery

## 서비스 역할
DPYB(Don't Paw Get Your Book)의 **AI · 탐색(Discovery) 전담 마이크로서비스**.
도서 원본 데이터의 소유권은 Basic API 서버에 있고, 이 서비스는 탐색·추천에 최적화된
읽기 전용 복제본(CQRS Read Model)과 벡터 인덱스를 소유한다.

### 담당 기능
1. **Custom RAG 도서 추천 챗봇** — 자연어 질의를 임베딩해 pgvector 유사도 검색으로
   후보 도서를 뽑고, 사서(Librarian) 페르소나 프롬프트로 추천 답변을 생성한다.
2. **시간대/테마 기반 큐레이션** — 요청 시각을 룰에 매칭해 테마를 결정하고
   해당 테마의 도서 목록을 반환한다.
3. **도서 데이터 동기화** — Basic API가 전달한 도서 payload에서 임베딩을 추출하고
   읽기 전용 복제 DB에 멱등하게 upsert한다.

## 기술 스택
| 구분 | 선택 |
| --- | --- |
| 언어/런타임 | Python 3.12 |
| 웹 프레임워크 | FastAPI (async) |
| 검증/직렬화 | Pydantic V2 (`ConfigDict(from_attributes=True)`) |
| ORM | SQLAlchemy 2.x Async + asyncpg |
| DB | PostgreSQL 16 + pgvector (HNSW) + tsvector (GIN, 전문검색) |
| 마이그레이션 | Alembic |
| 캐시/세션 | Redis 7 (redis.asyncio) — 대화 세션 관리 |
| LLM/임베딩 | AWS Bedrock via boto3 (현재 Mock 구현으로 대체) |
| 패키지 관리 | uv (`pyproject.toml` + `uv.lock`) |
| 정적 분석 | ruff, mypy |
| 테스트 | pytest, pytest-asyncio, pytest-mock, testcontainers, httpx |

## 시스템 구성
```
클라이언트 ──▶ /chat, /curations/time-based ─┐
Basic API ──▶ /internal/sync-book ──────────┤
                                            ▼
                        FastAPI (backend-discovery)
                                            │
              ┌──────────────┬──────────────┴────────────┐
              ▼              ▼                           ▼
   PostgreSQL+pgvector    Redis                  AWS Bedrock
   (읽기 전용 복제)      (대화 세션)              (현재 Mock)
```

## 패키지 구조 / 컨벤션
- 레이어: `domain` → `application` → `infrastructure` / `api`. 의존 방향은 안쪽으로만.
- `domain`은 계산·상태 변경·값 반환까지만 책임진다. 커밋·외부 API 호출은 `application`이 수행.
- ORM 모델은 `infrastructure/persistence/models.py`에만 존재하고, 레이어 밖으로는
  반드시 Pydantic 스키마로 직렬화해서 넘긴다(AsyncSession 컨텍스트 종료 전 파싱 완료).
- 외부 의존성(Bedrock, Redis, 현재 시각)은 Protocol + DI로 주입해 결정론적으로 테스트한다.
- 응답 스키마는 목록용/상세용을 분리하고, 목록 쿼리는 To-One 연관관계만으로 완성한다.
- 설정값은 `core/config.py`의 pydantic-settings로만 읽고, 접속 정보 기본값을 코드에 두지 않는다.

### 목표 디렉토리 구조
```
backend-discovery/
├── .harness/            HANDOFF · STATE · ARCHITECTURE · DECISIONS · BACKLOG · PLAN
├── docs/api/            openapi.yaml · README.md · decisions/
├── src/discovery/
│   ├── main.py
│   ├── core/            config.py(pydantic-settings) · exceptions.py · logging.py
│   ├── db/              session.py(async engine) · base.py
│   ├── domain/          book/ · curation/ · chat/
│   ├── application/     chat_service.py · curation_service.py · sync_service.py
│   ├── infrastructure/
│   │   ├── persistence/ models.py · book_repository.py
│   │   ├── llm/         protocols.py · mock_bedrock.py · factory.py
│   │   └── cache/       redis_client.py · chat_session_store.py
│   └── api/
│       ├── deps.py
│       ├── schemas/     chat.py · curation.py · sync.py
│       └── v1/routers/  chat.py · curations.py · internal.py
├── alembic/ · alembic.ini
├── tests/               unit/ · integration/ · conftest.py
├── docker-compose.yml · .env.example · pyproject.toml · uv.lock
```

## 데이터 모델 (읽기 모델)
- `books` — `book_id`(외부 식별자, unique), 제목·저자 등 탐색용 비정규화 컬럼,
  `category text`(원본 그대로, 파싱 없음), `embedding vector(1536)`,
  `search_vector tsvector`(`description + category` 결합, 키워드 전문검색용), `synced_at`
- 인덱스: `embedding`에 HNSW(`vector_cosine_ops`), `search_vector`에 GIN
- 검색: 기본은 벡터 유사도 단독 검색. 벡터 + `search_vector` 키워드 하이브리드는
  옵션 파라미터로 켤 수 있으나 기본 비활성 (`.harness/DECISIONS.md` 참고)

## 외부 계약
API wire 계약은 이 문서가 아니라 `docs/api/openapi.yaml`이 소유한다.
계약 결정 근거는 `docs/api/decisions/`를 참조한다.
