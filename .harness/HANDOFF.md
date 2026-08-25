# HANDOFF — backend-discovery

세션마다 무엇을 했는지 append-only로 기록한다.

## 2026-08-19 — 하네스 스캐폴딩 및 계획 수립
- 브랜치: `CLIAR-21-FastAPI-Scaffolding` (develop 분기)
- `AGENTS.md` 정독 후 `.harness/` 6종 문서와 `docs/api/` 뼈대를 생성했다.
- 정책 충돌 2건을 사용자와 확정: 의존성 파일은 `pyproject.toml`(uv) 채택, `docs/api/` 계약 산출물 선행 작성.
- `AGENTS.md`의 origin 주소가 `backend-book.git`으로 잘못 적혀 있어 `backend-discovery.git`으로 정정했다.
- 코드는 작성하지 않았다. `PLAN.md`에 3스텝 체크리스트만 확정한 상태로 종료한다.

### 다음 세션이 할 일
1. `PLAN.md` Step 1의 첫 항목(`pyproject.toml` 작성)부터 착수.
2. 커밋·push·PR은 사용자가 별도 요청할 때까지 수행하지 않는다.
3. 체크리스트 항목을 끝낼 때마다 `PLAN.md`에서 제거하고 `STATE.md`에 단계 한 줄로 반영한다.


## 2026-08-20 — CLIAR-21 인프라 세팅(Task 1~4) 완료, 브랜치명 정정
- CLIAR-21 인프라 세팅(Task 1~4: pyproject.toml/uv, docker-compose/Dockerfile, FastAPI 앱+/health, Alembic+테스트 픽스처)을 모두 완료했다.
- 로컬 브랜치명을 `CLIAR-21-FastAPI-Scaffolding`에서 `CLIAR-21-Infra-Setup`으로 rename했다(`git branch -m`). Jira 티켓 제목도 "인프라 세팅"으로 이미 수정 완료된 상태다.
  - 주의: 로컬 브랜치는 여전히 `origin/CLIAR-21-FastAPI-Scaffolding`을 추적(tracking) 중이다. push하지 않았으므로 원격 브랜치명은 아직 이전 이름 그대로다. 원격도 맞추려면 별도로 push(및 필요 시 원격 브랜치 rename/재생성)가 필요하며, 이번 세션에서는 수행하지 않았다.
- 다음 스텝(기존 계획의 Step 2 핵심 코드 구현 / Step 3 API 라우터 구현에 해당하는 작업)은 별도 티켓으로 진행할 예정이나, 세부 범위와 분할 방식(하나의 티켓으로 묶을지, Step 2/Step 3을 나눌지 등)은 아직 미확정이다. 다음 세션에서 재논의한다.
- `PLAN.md`의 Step 2/3 항목은 사용자 지시에 따라 이번 세션에서 손대지 않고 그대로 두었다. 분리 여부·새 파일 구조(`PLAN-CLIAR-22.md` 등)는 다음 티켓 범위가 확정된 뒤 다시 논의한다.
- 이 세션은 CLIAR-21 마감으로 종료한다. 코드/문서 추가 작업 없음.

### 다음 세션이 할 일
1. 다음 티켓 번호와 범위(Step 2/3의 분할 방식)를 사용자로부터 받아 `PLAN.md` 처리 방식을 논의한다.
2. 원격 브랜치명을 로컬과 맞출지(push 방식) 사용자와 확인한다.
3. 커밋·push·PR은 사용자가 명시적으로 요청할 때까지 수행하지 않는다.


## 2026-08-21 — CLIAR-40 착수
- CLIAR-21 PR이 `develop`에 머지된 것을 확인(`git pull`로 `origin/develop`이 `36728f7`로 갱신됨).
- `develop`에서 `CLIAR-40-Core-Implementation` 브랜치를 새로 분기했다.
- AWS 계정이 확보되어 Bedrock 등 실제 AWS 리소스 접근이 가능해졌다. 다만 로컬 개발 단계는 Mock을 기본으로 유지하고, 기존 `LLM_PROVIDER=mock|bedrock` 스위치로 실 Bedrock 전환이 가능하게 Task 7을 설계하기로 했다(별도 `USE_REAL_BEDROCK` 플래그는 추가하지 않음 — `.harness/DECISIONS.md` 참고).
- `PLAN.md`를 CLIAR-40 범위(Task 5~8)로 갱신했다. Step 3(API 라우터, Task 9~13)은 이번 티켓 범위 밖이며 별도 티켓이 확정되면 다시 반영한다.
- 이번 티켓부터는 Task 완료 보고에 사용자가 직접 확인할 수 있는 방법(터미널 명령, psql 조회, /docs 확인 등)을 포함하기로 합의했다.

### 다음 세션이 할 일
1. Task 5(pgvector 모델링 + tsvector/GIN + 마이그레이션)부터 착수.
2. 매 Task 완료 시 텍스트 보고와 함께 직접 확인 가능한 검증 방법을 제시하고 사용자 승인을 기다린다.


## 2026-08-21 — CLIAR-40 Task 5~8 전체 완료
- CLIAR-40(핵심 코드 구현) 범위였던 Task 5~8을 모두 완료했다. 각 Task는 완료 보고 시
  사용자가 직접 확인 가능한 방법(psql, redis-cli, pytest 명령, 환경변수 오버라이드 등)을
  제시하고, 사용자가 실제로 실행해 확인한 뒤 승인받는 방식으로 진행했다.
  - Task 5: `books` 모델(HNSW/embedding, GIN/search_vector generated column), 마이그레이션 2건.
  - Task 6: `BookSummary`/`BookDetail` DTO, `BookRepository`(upsert 멱등, 벡터+하이브리드 검색).
  - Task 7: `EmbeddingClient`/`ChatCompletionClient` Protocol, Mock 구현(결정론적), 실제
    `boto3` `bedrock-runtime`을 호출하는 `BedrockClient`. `LLM_PROVIDER`(기본 mock) 스위치로
    선택. 단위 테스트는 `boto3.client`를 `mocker.patch`로 대체해 실제 AWS 호출 없이 검증
    (AWS 자격증명 unset 상태에서도 통과함을 사용자가 직접 확인).
  - Task 8: Redis `ChatSessionStore`(RPUSH+LTRIM, sliding window TTL). 최대 턴 수와 TTL은
    `core/config.py`의 `chat_history_max_turns`/`chat_session_ttl_seconds`로 뽑아 환경변수
    (`CHAT_HISTORY_MAX_TURNS`, `CHAT_SESSION_TTL_SECONDS`)로 조절 가능하게 했다.
- 커밋은 Task 단위로 5개 분리 생성(`ba38475`~`c62c083`). 사용자 지시로 pre-commit
  훅(Git 정책/ruff/mypy/커밋 메시지 검증) 관련 변경도 별도 커밋으로 분리했다.
- 진행 중 실제 코드 버그 2건을 테스트가 잡아냄: (1) `bedrock_client.py`에서
  `payload["embedding"]` 직접 접근으로 의도한 `ValueError` 대신 `KeyError`가 나던 문제 →
  `payload.get(...)`으로 수정. (2) 테스트에서 mypy 변수 타입 재사용으로 인한 오추론(별개
  이슈, 변수명 분리로 해결).
- mypy strict 대응: `pgvector`/`testcontainers`/`boto3`는 `[[tool.mypy.overrides]]`로
  `ignore_missing_imports` 처리했지만, `redis`는 `py.typed`가 실제로 있어 override 대신
  호출부마다 `typing.cast`로 처리했다(모듈 전체를 무시하면 실제 타입 에러를 놓칠 위험이
  있어서 — `.harness/DECISIONS.md` 참고).
- push/PR은 아직 하지 않았다. 사용자가 diff를 직접 확인한 뒤 별도로 요청할 예정이다.

### 다음 세션이 할 일
1. 사용자가 diff 확인 후 push/PR 여부와 방식을 지시하면 그에 따라 진행한다
   (`git push -u origin CLIAR-40-Core-Implementation` 등, CLIAR-21 때와 유사한 흐름 예상).
2. PR 생성 시 base 브랜치가 `develop`으로 명시적으로 잡히는지 확인한다
   (CLIAR-21 때 GitHub 원격 HEAD가 `main`으로 잡혀 있던 이력이 있음 — 재확인 필요).
3. CLIAR-40 이후 범위(기존 계획의 Step 3, API 라우터 Task 9~13)는 아직 새 티켓 번호가
   없다. 사용자가 새 티켓을 알려주면 `develop`에서 새 브랜치를 분기하고 `PLAN.md`를 그
   범위로 갱신한다.



## 2026-08-21 — 방향 전환: 벡터DB/RAG 폐기, 사서 에이전트 별도 레포 이관 착수
- CLIAR-51 Task 9(계약 확정)까지 커밋(`269ef7d`)한 상태에서 Task 10(`/internal/sync-book`)
  구현(SyncService, 라우터, 단위/E2E 테스트)까지 마쳤으나 미커밋 상태였다. Docker 미기동으로
  통합 테스트는 실행하지 못한 채 대기 중이었다.
- 이 시점에 사용자가 새로운 조사(CLIAR-51과 무관, 코드 변경 없음)를 요청: (1) S3 Vectors
  전환 검토, (2) Strands Agents SDK 도입 설계(PoC). 두 조사 결과를 `.harness/research/`에
  각각 문서로 남겼다. S3 Vectors는 비권장(규모/쿼리빈도/하이브리드검색 요구사항 모두
  불일치) 결론, Strands는 선택지만 제시(판단은 사용자가 팀 논의 후 결정하도록 함).
- 조사 직후 사용자가 큰 방향 전환을 확정: 벡터DB(pgvector) 기반 자체 벡터 인덱스와 검색을
  backend-discovery에서 전부 폐기. 사서 페르소나·큐레이션·RAG 대화 기능은 별도 레포
  ("사서 에이전트 서버")로 이관해 웹 검색 도구 + 장기 메모리 기반 Strands Agents SDK로
  재설계. `ChatSessionStore`(Redis)는 backend-discovery에 유지하고 사서 에이전트 레포가
  API로 사용(Redis 직접 공유 안 함). 근거는 `.harness/DECISIONS.md` 최상단 참고.
  - **중요한 정정**: 처음에 "RAG 카탈로그 검색 기능 폐기"로 기록했으나, 사용자가 이후
    "자연어 질의 기반 도서 추천 기능 자체는 없어지는 게 아니라 웹 검색 도구를 쓰는
    에이전트로 재구현되는 것"이라고 정정했다. DECISIONS.md, archive README, STATE.md
    표현을 모두 이에 맞춰 수정했다. 다음 세션에서 이 뉘앙스를 다시 혼동하지 않을 것.
- 폐기 대상 코드는 **삭제하지 않고** `archive/vector-search-poc/`로 이동(원래 경로 구조
  유지): `domain/book/`, `infrastructure/persistence/book_repository.py`,
  `infrastructure/llm/`(protocols/mock_bedrock/bedrock_client/factory 전체),
  `api/schemas/book.py`, alembic 마이그레이션 2건(pgvector 확장, books 테이블), CLIAR-51
  Task 10 코드 전부(`application/sync_service.py`, `api/v1/routers/internal.py`,
  `api/schemas/sync.py`), `docs/api/openapi.yaml`(이전 버전 3개 엔드포인트 전체),
  `docs/api/decisions/0001-internal-sync-contract.md`. `archive/vector-search-poc/README.md`에
  폐기 사유·원 티켓·이관 예정을 기록했다.
- `docs/api/openapi.yaml`은 `paths: {}`인 최소 스켈레톤으로 재작성. `alembic/env.py`에서
  `Book` 모델 import 제거(현재 `Base.metadata`에 등록된 모델 없음). `main.py`/`api/deps.py`에서
  벡터/LLM/sync 관련 함수·라우터 등록 제거. `pyproject.toml`에 `archive/`를 ruff/mypy 검사
  대상에서 제외(`extend-exclude`, `exclude`) 추가. `uv run ruff check . && uv run mypy .`,
  `uv run pytest -m "not integration"`(1 passed, health만 남음) 통과 확인.
- `.harness/BACKLOG.md`의 CSV 배치 적재 항목 제거(벡터DB 폐기로 전제 자체가 사라짐).
  `.harness/STATE.md`: CLIAR-40 Task 5~7·CLIAR-51 Task 9~10은 "완료 후 폐기"로, Task 8만
  유효 완료로 표시, 방향 전환 자체를 별도 행으로 추가. `.harness/PLAN.md`: CLIAR-51 Task
  11~13 취소 명시, 전체를 새 구조로 재작성(보류 항목 + 사서 에이전트 레포 참고 안내).
- **7·8번(의존성 실제 제거, PostgreSQL 완전 제거, ERD)은 실행하지 않고 분석만 제시**했다.
  이유: 8번 조사 결과 "지금 RDB 테이블이 필요한 게 전혀 없다"는 결론이 나왔고, 이는
  PostgreSQL 자체를 이 레포에서 없앨 수 있다는 뜻인데, 그러면 "backend-discovery 레포
  자체의 존속 여부"라는 더 근본적인 질문이 생겨서 사용자가 여기서 멈추고 그 결정을 먼저
  하겠다고 했다. **다음 세션은 이 결정(레포 존속 여부)을 사용자에게 먼저 물어야 한다.**
- 이어서 사용자가 "웹 검색 기반 추천 에이전트에 어떤 모델을 쓸지, 속도를 어떻게
  최적화할지" 조사를 요청(사서 에이전트 레포 구현 참고용, backend-discovery 코드 변경
  없음). 결과를 `.harness/research/2026-08-21-librarian-agent-model-and-latency.md`에
  기록: 모델은 1차 Claude Haiku 4.5(agent 성능 최적화, tool use 검증됨), 대안 Nova Lite로
  A/B(단, 참고한 실측 비교는 Claude 3 Haiku 기준이라 4.5와 직접 비교 자료는 아직 없음
  — 구현 시 실측 필요). 속도 최적화는 우선순위 순으로 ①스트리밍 응답(Strands
  `stream_async` + FastAPI `StreamingResponse`) ②프롬프트 캐싱(고정된 system
  prompt/도구 정의) ③Bedrock Latency-Optimized Inference(리전/모델 가용성 구현 시
  재확인 필요 — 조사 시점엔 Claude 3.5 Haiku만 확인됨, 4.5 지원 여부 미확인)
  ④웹 검색 결과 캐싱(반복 질문 대응, `ChatSessionStore`와는 별개 저장소로 설계할 것)
  ⑤Strands native async 병렬 도구 실행.
- 커밋은 하지 않았다. git 변경사항(archive 이동 다수, pyproject.toml/main.py/deps.py/
  alembic/env.py 수정, .harness/* 문서 다수, docs/api/* 재작성)이 모두 미커밋 상태다.

### 다음 세션이 할 일
1. **가장 먼저: backend-discovery 레포 자체의 존속 여부를 사용자에게 확인한다.**
   `ChatSessionStore`만 남는 상태에서 이 레포를 계속 유지할지, 통합/폐기할지 등.
2. 레포 존속이 결정되면 `.harness/PLAN.md`의 "보류 중" 항목(PostgreSQL 관련 의존성·
   코드 제거, `ChatSessionStore` 최종 소유권 재확인)을 순서대로 처리한다.
3. 이번 세션에서 만든 미커밋 변경사항을 커밋할지 사용자에게 확인한다(Task 단위 분리,
   `[CLIAR-51]` 태그 규칙 적용 여부는 이 변경이 CLIAR-51 범위인지 별도 티켓인지부터
   판단 필요 — 방향 전환 자체가 새 티켓일 수 있음, 사용자 지시 필요).
4. 사서 에이전트 새 레포 구현이 시작되면 이 레포의 `.harness/research/` 두 문서
   (Strands 설계, 모델/속도)를 그 레포 세션에 전달해 참고하게 한다.


## 2026-08-23 — CLIAR-51 PR 머지 완료, 브랜치 정리 및 다음 개선 계획 수립
- `CLIAR-51` PR(#4)이 머지 완료되어 `main`과 `develop` 브랜치에 정상 반영됨.
- `session_id: null` 유연 처리(Pydantic 422 픽스) 및 Claude 3 Haiku용 Bedrock 설정 최적화 커밋(`eaa87e2`) 완료.
- 프론트엔드(`my-reading-room`)와의 실시간 스트리밍 대화 연동 테스트 성공 확인.
- 머지 완료된 로컬 및 원격 피처 브랜치(CLIAR-20, CLIAR-21, CLIAR-40, CLIAR-51) 정리 완료.
- `.harness/PLAN.md`에 다음 작업(사서 답변 출력 포맷 구조화 및 프론트엔드 도서 등록 버튼 연동 등) 계획 수립 완료.


## 2026-08-23 — CLIAR-67 프론트엔드 도서 등록 연동 지원 (사서 추천 포맷 구조화 및 검색 최적화)
- 브랜치: `CLIAR-67-Librarian-Recommendation-Format` (`develop`에서 분기).
- 프론트엔드(`my-reading-room`)에서 추천 도서를 파싱하여 도서 등록 화면 이동 및 필드 자동완성을 수행할 수 있도록 백엔드 추천 에이전트 포맷과 검색 가이드를 고도화했다.
  - Task 1: `domain/librarian/agent.py`의 `LIBRARIAN_SYSTEM_PROMPT`에 `### 📖 {도서 제목}`, `- **저자**: {저자명}`, `- **추천 이유**: {추천 이유}` 형식의 마크다운 템플릿을 명시.
  - Task 2: `infrastructure/search/book_search_tool.py`의 `search_books` 도구 docstring 및 검색 가이드 최적화.
  - Task 3: `tests/unit/test_librarian_agent.py`에 마크다운 템플릿 검증 테스트 추가, 전체 정적 분석(`ruff`, `mypy`) 및 단위 테스트 25건 통과 완료.
- 커밋·push는 사용자 요청 대기 중.

### 다음 세션이 할 일
1. 프론트엔드(`my-reading-room`)에서 변경된 사서 응답 포맷 기반 파싱 및 도서 등록 바로가기 버튼 / 필드 자동완성 연동 확인.
2. 커밋/push/PR 생성 요청 시 진행 (`[CLIAR-67]` 태그 사용).


## 2026-08-24 — CLIAR-86 오케스트레이터 에이전트 구축 및 프론트엔드 실연동 완료
- 브랜치: `CLIAR-86-Orchestrator-Agent` (`CLIAR-67-Librarian-Recommendation-Format` 헤드 `7c3bd1b`에서 분기).
- `CLIAR-67` 브랜치는 원격 `origin/CLIAR-67-Librarian-Recommendation-Format`으로 푸시 완료.
- Strands Agents SDK의 Agent-as-a-Tool 패턴을 적용하여 오케스트레이터가 최상위 진입점으로서 (1) 도서 추천 에이전트(로컬 도구), (2) 사서 에이전트(HTTP 원격 도구)로 라우팅하는 아키텍처를 완성했다:
  - Task 1: `domain/orchestrator/agent.py`(`create_orchestrator_agent`), `application/orchestrator_service.py`(`OrchestratorService`), `core/config.py`의 `orchestrator_model_id` 분리.
  - Task 2: `domain/orchestrator/tools/recommend_tool.py`(`RecommendBooksTool`) 로컬 도구 장착 (세션 중복 조회 방지).
  - Task 3: `domain/orchestrator/tools/librarian_tool.py`(`ConsultLibrarianTool`) 사서 에이전트 HTTP 스텁 도구 및 fallback 처리 (`librarian_agent_url` 설정 추가).
  - Task 4: `api/deps.py` 및 `api/v1/routers/chat.py`를 오케스트레이터로 교체 및 `docs/api/openapi.yaml`, `.harness/ARCHITECTURE.md` 동기화.
  - Task 5: 단위 테스트 47건(`pytest -m "not integration"`) 및 Redis Testcontainers 통합 테스트(`test_chat_integration.py`) 통과 완료.
- **실제 연동 이슈 해결 및 안전장치 추가**:
  - AWS Bedrock MFA 세션 인증 안내(`scripts/aws_mfa_login.sh`).
  - 추천 에이전트/오케스트레이터에 요청 권수(1권/N권) 엄격 준수 규칙 명시.
  - Strands `stream_async`의 다양한 이벤트(`contentBlockDelta`, `delta`)를 포괄하는 `extract_chunk_from_event` 구현.
  - 상위 오케스트레이터 모델(Haiku)이 서두 멘트만 생성하고 도구 결과를 본문에 생략하는 현상을 방지하기 위해, `extract_fallback_text`를 통해 `toolResult` 마크다운(`### 📖 ...`)을 본문에 자동 결합하는 결정론적 안전장치 구축.
  - 프론트엔드(`my-reading-room`)와의 실시간 스트리밍 대화 및 도서 추천 카드/등록 버튼 정상 렌더링 확인 완료.

### 다음 세션이 할 일
1. `CLIAR-86` 브랜치 커밋 및 원격 push 완료.
2. 엔지니어링 고도화 착수:
   - 1단계: `recommend_books` 도구 시그니처에 `count: int = 1` 파라미터 구조화 적용.
   - 2단계: 직결 스트리밍 파이프라인(Direct Streaming Pipeline) 구축으로 응답 레이턴시 2~3초대로 단축.
   - 3단계: Pydantic Structured Output을 통한 JSON 응답 고도화.





## 2026-08-25 — CLIAR-103 도서 표준 장르 분류 API 신설 완료
- 브랜치: `CLIAR-103-Book-Genre-Classification` (`develop`에서 분기).
- OCR 및 외부 도서 메타데이터(제목, 저자, 비정형 원본 카테고리)를 DPYB 서비스의 ERD 16개 표준 장르 규격으로 분류하는 경량 REST API(`POST /api/v1/classify-genre`)를 구현했다:
  - Task 1: `docs/api/openapi.yaml` 계약 버전 0.4.0으로 갱신, `StandardGenre` (16개 Enum) 및 `BookClassificationRequest`/`BookClassificationResponse` Pydantic 모델 정의.
  - Task 2: 16개 표준 장르 분류 프롬프트(`GENRE_CLASSIFIER_SYSTEM_PROMPT`), 도메인 파서(`parse_classification_response`), 완화 키워드 매처(`match_standard_genre`), `GenreClassifierService` 구현 및 `genre_classifier_model_id` 환경변수 분리.
  - Task 3: `api/v1/routers/genre.py` 라우터 구현, `api/deps.py` 의존성 주입 배선, `main.py`에 라우터 등록.
  - Task 4: 도메인·서비스 단위 테스트 30건 및 API 라우터 단위 테스트 4건 (총 34건 신규 추가), 전체 정적 분석(`ruff`, `mypy`) 및 단위 테스트 81건 통과 완료.
  - Task 5: `docs/api/decisions/0002-book-genre-classification.md` (ADR 0002) 작성, `.harness/STATE.md`, `.harness/ARCHITECTURE.md`, `.harness/DECISIONS.md`, `.harness/HANDOFF.md` 문서 동기화 완료.
- 커밋·push는 사용자 승인 대기 중 (`[CLIAR-103]` 태그 사용).

### 다음 세션이 할 일
1. 사용자 승인 시 커밋 생성 및 원격 push (`git push -u origin CLIAR-103-Book-Genre-Classification`).
2. PR 생성 (base 브랜치: `develop`).
3. 후속 과제 논의:
   - `recommend_books` 도구 파라미터 구조화 (`count: int = 1`).
   - 직결 스트리밍 파이프라인(레이턴시 단축).
   - Pydantic Structured Output 적용.

- **후속 Enum 동기화 (`genre_type`)**:
  - `backend-book`의 16개 표준 `genre_type` Enum(`SCIENCE_FICTION`, `LITERARY_FICTION`, `POETRY_DRAMA`, `BUSINESS_ECONOMICS`, `ARTS`, `COMPUTER_IT`, `NONE` 등)과 `StandardGenre` 스키마 및 반환값을 100% 일치시킴.
  - 미식별 및 예외 시 `NONE` (`confidence: 0.0`)으로 graceful fallback 처리.
  - 관련 단위 테스트 98건 전체 통과 확인.


## 2026-08-25 — CLIAR-111 사서 에이전트 연동 계획 초안 작성 후 구조 재논의로 보류
- 브랜치 `CLIAR-111-Librarian-Agent-Integration`을 `origin/develop`에서 생성했다.
  (주의: `git switch -c ... origin/develop`로 만들어 upstream이 `origin/develop`을
  추적한다. 나중에 push할 때 `git push -u origin CLIAR-111-Librarian-Agent-Integration`으로
  추적 대상을 바로잡을 것.) CLIAR-103 작업은 `origin/develop`에 이미 머지 반영됨을 확인했다.
- 작업명 제안: 단순 "사서 엔드포인트 연결"보다 범위를 담는
  **"사서 에이전트 실연동 및 페르소나 라우팅"**을 제안했다(대안: "사서 에이전트 HTTP 연동 및
  사서 전환(switch_to) 처리"). 실제 범위가 URL 연결이 아니라 `librarian_id` 선택과
  `switch_to` 전환 처리라서.
- 사용자가 `backend-librarian` 확정 계약과 README를 공유했다. 이를 근거로 `.harness/PLAN.md`에
  CLIAR-111 계획 초안(선결 질문 Q1~Q6 + Task 1~7 + 리스크)을 작성했다. 코드를 읽어 확인한
  현재 격차: ① `ConsultLibrarianTool`이 `librarian_id`를 안 보냄 ② `switch_to` 미처리(세션별
  현재 사서 저장소 없음) ③ `as_tool()`이 `session_id`를 전달하지 않아 사서 측 멀티턴 문맥이
  매 턴 초기화됨(실질 누락) ④ `latitude`/`longitude` 미지원으로 stork 날씨 큐레이션이 항상
  서울 기본값 ⑤ 타임아웃 10초는 사서(Sonnet 3.5 + 날씨 도구)에 부족 가능. 부수 발견: 사서와
  discovery 모두 로컬 8000 포트를 쓴다(충돌), 사서 대화 메모리가 인메모리라 재시작·다중
  인스턴스에서 사서 측 문맥 유실.
- 사용자가 "오케스트레이터가 에이전트 둘을 도구처럼 쓰는 게 아니라 그냥 멀티툴 에이전트
  하나처럼 보인다"는 문제를 제기하며, 매 턴 "사서 판단 → 추천 검색 → 사서 재포장" 고정 3단
  파이프라인 안을 제시했다. 이에 대해 코드 근거로 냉정한 피드백을 제시했다(구현 변경 없음,
  분석만):
  - 전제 정정: `RecommendBooksTool.recommend()`는 함수가 아니라 `create_librarian_agent`로
    독립 Agent를 만들어 `invoke_async`를 돌린다(자체 프롬프트 + Tavily 도구). 사서도 README상
    완결된 에이전트다. 즉 지금도 구조적으로는 Agents-as-Tools다.
  - 애매함의 실제 원인 4가지: ① `ORCHESTRATOR_SYSTEM_PROMPT` 규칙 2·3이 마크다운 유지·권수
    엄수 등 실행 세부까지 지시(위임이 아니라 마이크로매니징) ② `extract_fallback_text`가
    `toolResult`를 결정론적으로 잘라 붙여 상위의 조합 역할을 무력화(체감의 최대 원인)
    ③ 하위 추천 에이전트가 stateless 단발 호출이라 함수처럼 보임 ④ 어떤 에이전트를 왜
    골랐는지 관측 로그가 없어 두 겹 판단이 보이지 않음.
  - 고정 3단 파이프라인의 문제: 순서를 고정하면 Workflow/Chain이 되어 LLM 오케스트레이터가
    오히려 불필요해진다. 턴당 LLM 왕복 3회(Sonnet 3.5×2 + Haiku)로 레이턴시·비용이 백로그의
    "2~3초대 단축" 목표와 충돌. 사서는 `/api/v1/chat`(완성된 사용자용 답변) 하나뿐이라 1·3단계에
    필요한 구조화 판단/재포장 엔드포인트가 없어 팀원 레포 변경에 종속. 3단계 자유 재포장은
    프론트 도서 등록이 의존하는 CLIAR-67 마크다운(`### 📖` 등)을 깨뜨릴 위험. 사서를 내부
    판단기로 쓰면 사서 인메모리 세션 오염과 `switch_to` 의미 붕괴, cat의 전 장르 추천 능력과
    추천 결정 중복 문제도 발생.
  - 권장안(이 레포 안에서 대부분 해결, 팀원 의존 없음): 오케스트레이터 프롬프트에서 실행
    세부 지시 제거 → 권수는 `recommend_books(query, count=1)` 시그니처로 내림 /
    `extract_fallback_text` 강제 결합 제거 또는 pass-through로 전환 / 하위 추천 에이전트에
    세션 히스토리 주입 + 부실 결과 시 자체 재검색 루프 허용 / 다단 조합은 강제가 아니라
    프롬프트 예시로 "허용"(Strands는 한 턴에 도구 다회 호출 가능하므로 필요할 때만 2단) /
    선택 근거·도구 호출 횟수를 로그·디버그 메타로 노출 / 역할 경계는 데이터 기준 분리
    (사서=상황 해석·페르소나·큐레이션 방향, 추천=실존 도서 검증·등록용 마크다운 생성).
  - 순차 조합 데모가 꼭 필요하면 팀원에게 요청할 것은 구조화 판단 엔드포인트 1개
    (예: `POST /api/v1/assess` → `{mood, genres[], needs_recommendation, persona_note}`)이고,
    재포장(3단계)은 사서로 돌려보내지 말고 discovery가 맡아 왕복 3회→2회로 줄이고 마크다운
    계약을 우리가 지키는 방식을 제안했다.
- 사용자가 사서 담당 팀원의 아이디어도 합쳐 구조를 다시 논의하겠다며 이 세션을 종료했다.
  `PLAN.md`의 CLIAR-111 초안은 "보류" 표기로 남겼다. 코드 변경·커밋은 하지 않았다
  (미커밋 변경은 `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서뿐).

### 다음 세션이 할 일
1. 팀원과 합의된 멀티 에이전트 조율 방식을 먼저 확정한다(위임 복구 권장안 / `assess`
   엔드포인트 신설 포함 2단 조합 / 그 외 팀원 제안). 확정 후 `PLAN.md`의 Q1~Q6·Task를
   재작성하고 결정 근거를 `.harness/DECISIONS.md` 최상단에 기록한다.
2. 구조가 어떻게 정해지든 남는 확정 작업(계약 연결): `librarian_id` 전달, `switch_to`
   기반 세션 라우팅, `as_tool()`의 `session_id` 미전달 수정, 타임아웃 상향, 로컬 포트 정리.
3. 사서 응답 샘플을 받아 CLIAR-67 마크다운 포맷 준수 여부를 확인한다(프론트 도서 등록
   버튼 파손 여부 판단에 필요).


## 2026-08-25 — CLIAR-91 추천 에이전트 엔지니어링 고도화 완료
- 브랜치: `CLIAR-91-Agent-Engineering-Optimization` (`develop` 최신 헤드에서 분기).
- 최상위 오케스트레이터 에이전트의 Agents-as-Tools 아키텍처 하에서, 도서 추천 로컬 서브 에이전트(`recommend_books`) 및 추천 시스템 전반을 소프트웨어 엔지니어링 관점(결정론적 아키텍처)으로 고도화했다:
  - Task 1: `domain/librarian/post_processor.py`에 순수 함수 `truncate_books_by_count(markdown, count)` 구현 (헤더 `### 📖` 분할, 서두 Preamble 보존, 비정형/미달/음수 시 원본 무손실 반환). `RecommendBooksTool`에 `count: int = 1` 파라미터 구조화, docstring `Args:` 스키마 명시, clamp(1~5) 적용, 프롬프트 생성량 유도 및 반환 지점 후처리 상한 강제 결합 완료.
  - Task 2: `infrastructure/search/book_search_tool.py` docstring에 출판사/쪽수 검색 힌트 반영. `domain/librarian/agent.py`의 `LIBRARIAN_SYSTEM_PROMPT`에 `- **저자**: {저자명} ({페이지수}쪽)` 템플릿 및 쪽수 미확인 시 유연 처리 규칙 추가 (프론트엔드 300쪽 fallback 현상 해소).
  - Task 3: 사서 및 오케스트레이터 시스템 프롬프트에 불필요한 과잉 사과("죄송합니다...") 금지 지침 및 전문적이고 신뢰감 있는 사실 기반 톤앤매너 규칙 추가.
  - Task 4: 스트리밍 및 오케스트레이션 파이프라인 안정성 점검 완료 및 향후 직결 스트리밍 파이프라인 전환 설계 메모 정리.
  - Task 5: 단위 테스트 106건(`pytest -m "not integration"`) 및 Redis Testcontainers 통합 테스트 15건(`pytest -m "integration"`), 정적 분석(`ruff`, `mypy`) 100% 통과 완료.
- 커밋·push는 사용자 승인 대기 중 (`[CLIAR-91]` 태그 사용).

### 다음 세션이 할 일
1. 사용자 승인 시 커밋 생성 및 원격 push (`git push -u origin CLIAR-91-Agent-Engineering-Optimization`).
2. PR 생성 (base 브랜치: `develop`).
3. 후속 과제 진행:
   - CLIAR-111 사서 에이전트 실연동 및 페르소나 라우팅 재개.
   - 직결 스트리밍 파이프라인(Direct Streaming Pipeline) 구축 (레이턴시 단축 및 증분 Early Stop).
