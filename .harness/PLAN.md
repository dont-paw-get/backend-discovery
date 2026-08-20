# PLAN — backend-discovery (CLIAR-40-Core-Implementation)

## CLIAR-40. 핵심 코드 구현
- [ ] Task 6: Pydantic V2 DTO + BookRepository
- [ ] Task 7: Bedrock Mocking 계층 (Mock 기본, LLM_PROVIDER 스위치로 실 Bedrock 전환 가능하게 설계)
- [ ] Task 8: Redis 비동기 대화 세션 스토어

---

## Task 상세

### CLIAR-40 — 핵심 코드 구현
(원래 계획의 Step 2에 해당. Step 3 API 라우터 구현은 CLIAR-21 범위 밖으로 분리되었고,
별도 티켓 범위가 확정되면 새 PLAN 섹션으로 옮긴다. 지금은 이 파일에 손대지 않는다.)

**Task 6: Pydantic V2 DTO와 BookRepository**
- 목표: 영속성과 프레젠테이션을 분리하고 조회 로직을 리포지토리로 캡슐화한다.
- 가이드: `api/schemas/`에 목록용(`BookSummary`)·상세용(`BookDetail`) 분리, `model_config = ConfigDict(from_attributes=True)` 명시. `BookRepository`에 `upsert(book)`(`ON CONFLICT DO UPDATE`, `search_vector` 갱신 포함), `search_by_embedding(vector, filters, limit, use_hybrid_search=False)`. 세션 종료 전 `model_validate`로 파싱 완료해 `MissingGreenlet` 차단. 페이징 쿼리에 To-Many `joinedload` 금지.
- 테스트: 통합 — upsert 멱등성(같은 `book_id` 두 번 → 1행, 값 갱신), 벡터 검색과 하이브리드 검색(옵션 on) 결과 비교. 단위 — DTO 직렬화 필드 검증.
- Demo: 리포지토리 호출만으로 도서를 저장·갱신하고 Pydantic DTO 리스트를 돌려받는다.

**Task 7: Bedrock Mocking 계층**
- 목표: AWS 미연동 상태에서 임베딩·챗 응답을 결정론적으로 제공하고, 실연동으로 갈아끼울 수 있게 한다.
- 배경: AWS 계정이 확보되어 실제 Bedrock 리소스 접근이 가능해졌다. 다만 로컬 개발 단계에서는 Mock을 기본값으로 유지하고, 이미 존재하는 `LLM_PROVIDER=mock|bedrock`(`core/config.py`) 스위치로 실 Bedrock 전환이 가능하게 설계한다. 별도의 `USE_REAL_BEDROCK` 같은 boolean 플래그는 추가하지 않는다 — `LLM_PROVIDER`가 이미 같은 역할(구현 선택)을 하므로 스위치를 이중화하면 두 값이 어긋날 위험이 있다.
- 가이드: `infrastructure/llm/protocols.py`에 `EmbeddingClient.embed(texts) -> list[list[float]]`, `ChatCompletionClient.complete(messages) -> str` Protocol. `mock_bedrock.py`는 입력 문자열 해시를 시드로 1536차원 정규화 벡터 생성(같은 입력 → 같은 벡터), 챗은 사서 페르소나 템플릿에 후보 도서를 채운 고정 문구 반환. `factory.py`가 `settings.llm_provider`로 구현 선택, `api/deps.py`에서 주입. `LLM_PROVIDER=bedrock`일 때 실제로 `boto3` `bedrock-runtime` 클라이언트를 생성하는 `BedrockClient`도 함께 구현한다(이번 Task 범위, AWS 계정 확보로 실 코드 작성 가능). 단, 기본값은 여전히 `mock`으로 두고, `.env.example`에 `LLM_PROVIDER=mock`이 기본값임을 주석으로 명시한다. **boto3 타입 스텁 판단 순서**: 먼저 스텁 없이 `uv run mypy .`를 실행해 strict 모드에서 `boto3.client(...)` 호출부에 에러(예: 반환 타입 `Any`로 인한 unreachable/no-any-return 등)가 나는지 확인한다. 에러가 있으면 `mypy-boto3-bedrock-runtime`(Task 1 조사 시점 최신 안정: `1.43.62` 기준 상한 핀)을 dev 그룹에 추가하고 재검증한다. 에러가 없으면 스텁 없이 진행하고 `.harness/DECISIONS.md`에 그 판단과 근거를 기록한다.
- 테스트: 단위 — Mock: 동일 입력 반복 시 벡터 동일, 차원 정확히 1536, L2 노름 ≈ 1, 다른 입력은 다른 벡터. Bedrock: `boto3` 클라이언트 호출을 mocker로 대체해 요청 페이로드 조립과 응답 파싱만 검증(AWS 계정으로 실제 호출은 하지 않음 — 비용·네트워크 의존 없는 단위 테스트 유지).
- Demo: `LLM_PROVIDER=mock`(기본값)으로 임베딩 벡터와 사서 톤 답변을 즉시 얻는다. `.env`에서 `LLM_PROVIDER=bedrock`으로 바꾸고 유효한 AWS 자격증명을 주입하면 동일한 인터페이스로 실제 Bedrock 응답을 받을 수 있음을 코드 경로로 보여준다(실제 호출은 사용자 확인 후 별도로 검증).

**Task 8: Redis 비동기 대화 세션 스토어**
- 목표: 멀티턴 대화 문맥을 TTL과 함께 비동기로 저장·조회한다.
- 가이드: `redis.asyncio` 커넥션 풀을 lifespan에서 관리. `ChatSessionStore`에 `append_turn`, `get_history`, `clear`. 키는 `chat:session:{session_id}`, RPUSH + LTRIM으로 최근 N턴만 유지, 매 쓰기마다 `EXPIRE` 갱신. `session_id`는 서비스가 생성하지 않고 주입받는다(없으면 라우터 의존성에서 발급).
- 테스트: 통합 — append→get 순서 보장, LTRIM 상한, TTL 설정, clear 후 빈 히스토리.
- Demo: 같은 `session_id`로 여러 turn을 넣고 순서대로 조회되며 TTL이 걸려 있음을 확인한다.

### Step 3 — API 라우터 구현

**Task 9: `docs/api/` 계약 산출물 확정**
- 목표: 코드보다 먼저 wire 계약을 확정한다.
- 가이드: `docs/api/openapi.yaml`에 3개 엔드포인트의 경로·요청/응답 스키마·에러 응답(400/401/404/422/503)과 `X-Internal-Token` securityScheme 정의. `docs/api/README.md`에 문서 탐색·검증 방법. `docs/api/decisions/0001-internal-sync-contract.md`에 "Basic API가 push하는 단건 동기 HTTP 방식 채택" ADR. `.harness`에 이 내용을 복제하지 않고 참조만.
- 테스트: OpenAPI 스펙 유효성 검사 통과.
- Demo: 스펙 파일을 Swagger UI/Redoc에 넣으면 3개 엔드포인트 계약을 열람할 수 있다.

**Task 10: `POST /internal/sync-book`**
- 목표: Basic API가 보낸 도서 데이터를 임베딩해 읽기 모델에 멱등 반영한다.
- 가이드: `SyncService.sync(payload)`가 임베딩 대상 텍스트(제목+저자+설명+category)를 조립해 `EmbeddingClient`로 벡터를 얻고 `BookRepository.upsert` 호출(`search_vector`도 같은 upsert에서 갱신). 커밋은 서비스 계층. 라우터에 `verify_internal_token` 의존성 부착. 스키마는 openapi.yaml과 1:1.
- 테스트: 단위 — mocker로 임베딩/리포지토리 대체, 반환 결과와 조립된 임베딩 입력 텍스트 검증. E2E — 토큰 없으면 401, 유효 요청 200 + DB 1행, 재전송 시에도 1행(멱등).
- Demo: curl 한 번으로 도서를 동기화하고, 두 번 호출해도 중복 없이 갱신되는 것을 DB에서 확인한다.

**Task 11: `GET /curations/time-based`**
- 목표: 요청 시각을 테마로 매핑해 큐레이션 목록을 반환한다.
- 가이드: `domain/curation/time_rules.py`에 순수 함수 `resolve_theme(now) -> Theme`(새벽/아침/오후/저녁/심야 구간 룰). `datetime.now()` 내부 호출 금지, 라우터 의존성 `get_now`로 주입. `CurationService`가 테마에 맞는 키워드로 `search_vector` 기반 검색(또는 하이브리드 검색)을 호출 후 목록용 DTO 반환. 쿼리에 하드코딩 조건·비결정적 함수 금지.
- 테스트: 단위 — 경계 시각(구간 시작/끝, 자정 넘김) 파라미터라이즈. E2E — `get_now` 오버라이드로 시각 고정해 테마·목록 검증.
- Demo: 시각을 주입해 오전/심야 각각 다른 테마와 도서 목록이 나온다.

**Task 12: `POST /chat` — RAG 파이프라인 조립**
- 목표: 자연어 질의에 사서 페르소나로 도서를 추천한다.
- 가이드: `ChatService.answer(session_id, message)` — ① Redis 히스토리 로드 ② 질의 임베딩 ③ pgvector 유사도 검색(top-k, 옵션 필터) ④ 검색 결과 + 히스토리로 사서 페르소나 프롬프트 조립 ⑤ `ChatCompletionClient.complete` ⑥ 사용자·어시스턴트 턴 Redis append ⑦ 답변 + 근거 도서 목록 반환. DB 세션 안에서 Pydantic 파싱을 마친 뒤 프롬프트 조립.
- 테스트: 단위 — mocker로 임베딩·검색·LLM·세션 스토어 대체, 반환 DTO(답변, 근거 도서, session_id)와 히스토리 append 부작용 검증. E2E — 같은 `session_id` 2회 호출 시 두 번째 프롬프트에 이전 턴 포함 확인.
- Demo: "비 오는 날 읽을 따뜻한 소설 추천해줘"에 사서 톤 답변과 근거 도서 목록이 오고, 후속 질문에서 문맥이 유지된다.

**Task 13: 최종 배선과 계약 정합성 검증**
- 목표: 흩어진 라우터·의존성을 앱에 통합하고 코드와 계약이 일치함을 보증한다.
- 가이드: `api/v1/routers/`를 `create_app()`에 등록(`/chat`, `/curations`는 공개 prefix, `/internal`은 별도 prefix + 토큰 의존성). 예외 핸들러로 도메인 예외 → HTTP 상태 매핑. FastAPI 생성 스키마와 `docs/api/openapi.yaml` 비교 계약 테스트 추가. orphan 코드 없는지 확인.
- 테스트: `uv run ruff check . && uv run mypy . && uv run pytest -m "not integration"` 통과 후, 계약 테스트 포함 `pytest` 전체 통과(사용자 요청 시).
- Demo: `docker compose up` + 서버 기동으로 3개 엔드포인트가 실제 DB·Redis·Mock LLM을 통해 end-to-end 동작하고, `/docs`가 `docs/api/openapi.yaml`과 일치한다.

---

## 함께 갱신할 산출물 (AGENTS.md 동기화 정책)
- Task 1 완료 시 → `.harness/ARCHITECTURE.md` 기술 스택 표 확정
- Task 5·9 완료 시 → `docs/api/openapi.yaml` 및 필요 시 `docs/api/decisions/` ADR 추가
- 각 Task 완료 시 → `PLAN.md`에서 항목 제거 + `STATE.md` 단계 한 줄 갱신
- 세션 종료 시 → `.harness/HANDOFF.md` 인수인계 append
