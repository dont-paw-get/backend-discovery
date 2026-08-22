# archive/vector-search-poc — 폐기된 벡터DB/RAG 챗봇 PoC

이 디렉토리는 backend-discovery에서 **삭제 대신 보관**한 코드다. 원래 있던 경로
구조를 최대한 그대로 유지했으므로(`archive/vector-search-poc/<원래 상대 경로>`),
필요하면 참조하거나 새 레포로 복사하기 쉽다.

## 왜 폐기됐는가

2026-08-21, 방향 전환이 결정됐다:

- **벡터DB(pgvector) 기반 자체 벡터 인덱스와 그에 기반한 검색을 backend-discovery에서
  전부 폐기한다.** 단, **자연어 질의 기반 도서 추천 기능 자체는 폐기가 아니라
  재구현이다** — backend-discovery 자체가 Strands Agents SDK 기반 "추천 에이전트"
  역할을 계속 맡고, 웹 검색 도구(Tavily)로 실시간 조회해 추천한다. 즉 우리 DB의
  벡터 인덱스로 도서를 찾는 방식에서 에이전트가 웹 검색 도구로 실시간 조회해
  추천하는 방식으로 바뀌는 것이며, "질문하면 추천해준다"는 기능 자체는 유지된다.
- 초기에는 이 기능을 별도 "사서 에이전트 서버" 레포로 이관하는 방향을 검토했으나,
  세션 스토어(`ChatSessionStore`)까지 넘기면 backend-discovery에 남는 로직이
  없어진다는 문제로 재검토한 뒤, backend-discovery 자체가 추천 에이전트로
  존속하는 것으로 최종 결정됐다.
- 이 결정에 이르기까지 조사 문서들(`.harness/research/` 참고: S3 Vectors 검토,
  Strands Agents SDK 설계, 모델/속도 최적화)이 선행됐다.
- backend-discovery는 `ChatSessionStore`(Redis 기반 대화 세션 관리)를 계속 사용한다.
- 자세한 결정 근거는 `.harness/DECISIONS.md`(2026-08-21 항목)를 참고한다.

## 어떤 티켓에서 만들어졌는가

| 경로 | 티켓 | 내용 |
| --- | --- | --- |
| `domain/book/models.py` | CLIAR-40 Task 5 | `books` 읽기 모델 (pgvector HNSW, tsvector GIN generated column) |
| `infrastructure/persistence/book_repository.py` | CLIAR-40 Task 6 | `BookRepository` — upsert 멱등, 벡터/하이브리드 검색 |
| `api/schemas/book.py` | CLIAR-40 Task 6 | `BookSummary`/`BookDetail` DTO |
| `infrastructure/llm/protocols.py`, `mock_bedrock.py`, `bedrock_client.py`, `factory.py` | CLIAR-40 Task 7 | `EmbeddingClient`/`ChatCompletionClient` Protocol, Mock 구현, Bedrock 클라이언트, `LLM_PROVIDER` 스위치 |
| `alembic/versions/a677930b7b55_*.py` | CLIAR-40 Task 5 | pgvector 확장 활성화 마이그레이션 |
| `alembic/versions/b994c754f6d5_*.py` | CLIAR-40 Task 5 | `books` 테이블 생성 마이그레이션 (HNSW/GIN 인덱스) |
| `application/sync_service.py` | CLIAR-51 Task 10 | `SyncService` — 단건 도서 임베딩+upsert |
| `api/v1/routers/internal.py` | CLIAR-51 Task 10 | `POST /internal/sync-book` 라우터 |
| `docs/api/openapi.yaml` | CLIAR-51 Task 9 | `/chat`, `/curations/time-based`, `/internal/sync-book` 계약 전체 (폐기 전 마지막 버전) |
| `docs/api/decisions/0001-internal-sync-contract.md` | CLIAR-51 Task 9 | "`/internal/sync-book`은 실시간 단건 전용, 대량 적재는 CSV 배치" ADR |
| `tests/unit/`, `tests/integration/` | CLIAR-40, CLIAR-51 | 위 코드에 대한 단위/통합 테스트 |

CLIAR-51의 Task 9(계약), 11(큐레이션), 12(chat), 13(배선)은 착수 전 취소되어
이 아카이브에 없다 (`.harness/PLAN.md`, `.harness/STATE.md` 참고).

## 참고용 설계 자료

이 아카이브의 설계는 참고용으로 남아 있다(backend-discovery가 추천 에이전트로
재구현할 때 참고 가능):

- `infrastructure/llm/`의 Protocol 설계 — `EmbeddingClient`/`ChatCompletionClient`는
  이번 재구현에서 Strands `Agent`/도구 기반 설계로 대체된다
  (`.harness/research/2026-08-21-strands-agents-poc-design.md` 참고)
- `mock_bedrock.py`의 결정론적 Mock 구현 방식(테스트 전략 참고용)
- `domain/book/models.py`, `book_repository.py`의 벡터/하이브리드 검색 설계
  (참고용 — 새 구현은 벡터DB 없이 웹 검색으로 대체하므로 직접 재사용하지 않음)
