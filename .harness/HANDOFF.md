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


## 2026-08-26 — CLIAR-114 추천 에이전트 해외 도서 한국어 번역 지침 추가 및 프롬프트 정돈 완료
- 브랜치: `CLIAR-114-librarian-translation-guideline` (`develop` 최신 헤드에서 분기).
- 추천 에이전트(`src/discovery/domain/librarian/agent.py`의 `LIBRARIAN_SYSTEM_PROMPT`)가 해외 원서 추천 시 도서 제목·권차·저자명을 표준 한국어로 번역하도록 시스템 프롬프트 지침을 보강하고, 전체 규칙을 총 7개로 압축 정돈했다:
  - Task 1: `LIBRARIAN_SYSTEM_PROMPT`에서 기존 6번(사과 방지)과 7번(인사말)을 `6. 톤앤매너`로 압축 통합하고, 3번/7번에 역자/번역가가 아닌 원작자(글/그림 작가, 예: 아오야마 고쇼) 표기 지침과 `7. 해외 도서 번역` 규칙(제목, 권차, 저자명의 한국어 표준 명칭 번역)을 추가하여 총 7개 규칙 체계 확립.
  - Task 2: `tests/unit/test_librarian_agent.py`의 단위 테스트 assert 갱신, 정적 분석(`ruff`, `mypy`) 및 단위 테스트 106건 통과 완료.
  - Task 3: `.harness/BACKLOG.md`에 C안(비한글 패턴 감지 + Haiku 단발 호출 후처리 fallback 검토) 기술 부채 등록, `.harness/DECISIONS.md`, `.harness/STATE.md`, `.harness/PLAN.md` 하네스 산출물 동기화 완료.
- CLIAR-114 작업 완료 및 PR(#13) 머지(`develop`) 완료.
- 멘토링 피드백(원서 vs 정발본 인터랙티브 대화) 및 프론트엔드 모드 통합(단일 오케스트레이터 기반 올인원 에이전트) 제안 계획을 `.harness/PLAN.md`에 작성 완료.

### 다음 세션이 할 일
1. `.harness/PLAN.md`의 [제안] 단일 오케스트레이터 기반 올인원 독서 비서 계획 피드백 및 확정 논의.
2. Phase 1: `CLIAR-111` 사서 에이전트 실연동 및 페르소나 라우팅 착수.
3. Phase 2: 도서 추천 시 원서 vs 정발본 대화형 안내 및 정발본 재검색 체이닝 보강.
4. Phase 3 & 4: 내 서재 검색 / 독서 활동 관리 도구 신설 및 프론트 단일 챗 UI 연동.



## 2026-08-27 — CLIAR-111 사서 연동 계획 확정, 브랜치 정책 강화 및 브랜치 정리
- 이전 세션(CLIAR-111 초안, 2026-08-25)에서 사용자가 제기한 "오케스트레이터가 멀티툴
  에이전트처럼 보인다" 구조 논쟁을 이번 세션에서 별도로 재검토했다(피드백 요청 → 3단
  파이프라인 대안 검토 → 코드 근거로 기각, 위임 복구 권장안 유지). 이어서 사서 팀이
  `backend-librarian` API 명세(신호(`signals`: weather/time_of_day/mood/genre_focus),
  `switch_to` 사서 전환, 좌표 지원, Sonnet 3.5 모델)를 전달해 CLIAR-111을 실제로 계획
  단계로 진행했다.
- 코드 확인으로 명세와의 현재 격차 7건을 재확인: `librarian_id`/`session_id`/좌표 미전달,
  `switch_to`/`signals` 미처리, 타임아웃 10초 하드코딩, 로컬 포트 8000 충돌.
- 사용자와 5가지 설계 축을 확정했다(`.harness/DECISIONS.md` 2026-08-27 최상단 참고):
  1) signals→추천 반영은 서비스 강제 결합이 아니라 오케스트레이터 프롬프트 레벨 위임.
  2) 로컬 포트는 사서(8000) 대신 discovery를 8001로 이동.
  3) 좌표는 세션(로그인) 시작 시 1회만 수신해 세션 메타로 캐시, 재로그인 시 재수신.
  4) `switch_to`는 텍스트 안내가 아니라 `ChatResponse`에 구조화 필드로 통과(프론트가
     사서 전환 시 테마도 바꾸는 UI를 이미 갖고 있어서).
  5) 사서 HTTP 타임아웃은 실측 전까지 임시 20초로 상향, 환경변수로 분리.
  - 모델 통일(Haiku→Sonnet 3.5) 요청은 별도로 논의했으나, 사서 연동과 독립적인 축(비용·
    레이턴시·CLIAR-91/114 회귀 위험)이라는 이유로 이번 범위에서 제외하고
    `.harness/BACKLOG.md`로 분리하는 데 합의했다.
- `.harness/PLAN.md`를 CLIAR-111 확정 계획(Task 0~9)으로 재작성하고, 기존 "올인원 독서
  비서" 제안(2026-08-26 세션 산물)은 8/26에 제기했던 보안·구조 피드백(IDOR 위험, fallback
  결합 무차별 확대, 쓰기/읽기 혼재, 스트리밍 계약 변경)을 반영해 Phase 0~4로 재정렬해서
  같은 문서에 유지했다. 핵심: `search_my_library`는 discovery가 자체 CRUD를 만드는 게
  아니라 Basic API 기존 엔드포인트를 호출하는 프록시 도구이고, `user_id`는 도구 파라미터로
  LLM이 채우지 않고 인증 토큰에서 서버가 추출해 주입하는 방식(A안 패스스루 권장)으로
  못박았다 — 인증 방식 자체는 Basic API 팀 확인이 필요한 선결 항목으로 남겼다.
- **`AGENTS.md`에 "모든 PR/병합은 develop으로만" 규칙을 명문화**했다(기존엔 `develop→main`
  릴리스 병합 예외가 남아 있었음). 동시에 "머지 완료된 브랜치는 로컬+원격에서 정리한다"는
  절차(머지 확인 방법, 정리 전 사용자 확인)를 브랜치 정책에 추가했다.
- 위 정책에 따라 `develop`에 머지 완료가 확인된(`git merge-base --is-ancestor`) 피처
  브랜치 8개를 로컬(`git branch -d`)과 원격(`git push origin --delete`)에서 정리했다:
  `CLIAR-102-Fix-Duplicate-Chat-Router`, `CLIAR-103-Book-Genre-Classification`,
  `CLIAR-103-Book-Genre-Enum-Sync`, `CLIAR-114-librarian-translation-guideline`,
  `CLIAR-51-Recommendation-Agent`(원격만 존재), `CLIAR-67-Librarian-Recommendation-Format`,
  `CLIAR-86-Orchestrator-Agent`, `CLIAR-91-Agent-Engineering-Optimization`. `main`(develop
  대비 20커밋 behind)과 `deploy-dev`(배포용)는 건드리지 않았다.
- 코드 구현은 아직 착수하지 않았다. 이번 세션은 계획·정책·정리만 수행했다.

### 다음 세션이 할 일
1. `develop`에서 `CLIAR-111-...` 브랜치를 새로 분기하고 `PLAN.md`의 Task 1부터 순서대로
   착수한다(Task 0 선결 확인은 이미 완료 표시됨).
2. Task 2(API 계약 확장)는 `docs/api/openapi.yaml`을 먼저 수정하는 게 순서라는 점을
   `AGENTS.md` 동기화 규칙대로 지킨다.
3. Task별 완료 시 `PLAN.md`에서 항목을 지우고 `STATE.md`에 단계 한 줄로 반영한다.
4. "올인원 독서 비서" Phase 0~4는 CLIAR-111 완료 후 재논의 — 특히 Phase 2 착수 전
   Basic API 인증 패스스루 방식(A안) 확정이 팀원 의존 선결 조건이다.


## 2026-08-27 — CLIAR-111 사서 에이전트(backend-librarian) 실연동 및 세션/시그널 조율 구현 완료
- 브랜치: `CLIAR-111-Librarian-Agent-Integration` (`develop`에서 분기)
- CLIAR-111의 모든 구현 Task(Task 1~9)를 완료했다:
  - Task 1: `core/config.py` 및 `.env.example`에 `librarian_default_id: str = "cat"`, `librarian_http_timeout_seconds: float = 20.0` 분리 추가.
  - Task 2: `docs/api/openapi.yaml` 및 `src/discovery/api/schemas/chat.py`에 `latitude`, `longitude` (ChatRequest), `SwitchToSuggestion`, `switch_to` (ChatResponse) 추가. `api/v1/routers/chat.py`와 `OrchestratorService`에 좌표 전달 배선.
  - Task 3: `domain/orchestrator/librarian_response.py` DTO 모델(`WeatherSignal`, `LibrarianSignals`, `SwitchToSuggestion`, `LibrarianResponse`) 신설. `ConsultLibrarianTool`이 `LibrarianResponse`를 파싱하고 `session_id`, `librarian_id`, `latitude`, `longitude`를 서버 레벨에서 클로저로 주입하여 호출하도록 재작성(IDOR 취약점 원천 차단).
  - Task 4: `ChatSessionStore`에 세션별 활성 `librarian_id` 및 사용자 좌표를 sliding TTL로 관리하는 `get_session_meta`, `update_session_meta` 메서드 추가.
  - Task 5: `ConsultLibrarianTool` 호출 콜백을 통해 `switch_to` 제안을 감지하면 세션 메타의 `librarian_id`를 갱신하고 `ChatResponse.switch_to`로 클라이언트에 구조화된 객체 반환.
  - Task 6: `ConsultLibrarianTool` 반환 텍스트에 `[사서 분석 정보]`(포커스 장르, 무드, 날씨)를 포맷팅하여 LLM 컨텍스트에 제공하고, `ORCHESTRATOR_SYSTEM_PROMPT`에 해당 정보를 `recommend_books` 질의에 반영하도록 위임 지시 추가.
  - Task 7: `docker-compose.yml`의 discovery 포트를 `8001:8000`으로 분리하여 사서 서비스(`8000`)와의 로컬 충돌 해소.
  - Task 8: `test_librarian_tool.py`, `test_session_store.py`, `test_orchestrator_service.py`, `test_chat_router.py`, `test_orchestrator_routing.py` 단위 테스트 갱신 및 신설. 정적 분석(`ruff`, `mypy`) 100% 통과, 단위 테스트 110건 전체 통과.
  - Task 9: `docs/api/decisions/0003-librarian-agent-integration.md` ADR 작성 및 `.harness/ARCHITECTURE.md`, `.harness/STATE.md`, `.harness/PLAN.md` 갱신.

### 다음 세션이 할 일
1. 사용자 승인 시 커밋 생성, push 및 `develop` 대상 PR 생성.
2. CLIAR-111 완료 후 [제안] 단일 오케스트레이터 기반 올인원 독서 비서 (Unified Agent Assistant) 로드맵 검토 및 Basic API 인증 연동 선결 확인.


## 2026-08-28 — 자체 완결형 사서 페르소나/지능형 스위칭 내장, Sonnet 5 글로벌 CRIS 및 검색/UX 튜닝 완료
- 브랜치: `CLIAR-111-Librarian-Agent-Integration`
- 사서 서버(`backend-librarian`) 장애/에러 fallback과 무관하게 Discovery 자체에서 완벽하게 페르소나와 스위칭(`switch_to`)을 수행할 수 있도록 자체 완결형 아키텍처와 성능 튜닝을 완료했다:
  1. **자체 완결형 지능형 사서 페르소나 & 스위칭 엔진 내장**:
     - `ConsultLibrarianTool`: 원격 사서 서버가 fallback(예: "생각이 안 난다냥...")을 반환하거나 장애가 발생해도, Discovery 내부의 `evaluate_local_persona_response`가 즉시 개입.
     - **고양이 사서 (`cat`)**: SF, 판타지, 과학, 미스터리, 경영, 경제, 비즈니스, 투자 등 질문 시 `switch_to: stork` (황새/슈빌 사서) 자동 생성.
     - **황새 사서 (`stork`)**: 시, 힐링 에세이, 가벼운 일상 소설 등 질문 시 `switch_to: cat` (고양이 사서) 자동 생성.
  2. **Claude Sonnet 5 글로벌 CRIS (`global.anthropic.claude-sonnet-5`, `us-east-1`) 적용**:
     - Reasoning 모델의 토큰 소모를 방어하기 위해 `create_orchestrator_agent` 및 `create_librarian_agent`에 `max_tokens=2048` 주입.
  3. **도서 검색 도구 호출 최적화 (지연시간 70% 이상 단축)**:
     - `LibrarianAgent`가 책 1권마다 `search_books`를 6~9번씩 반복 호출하던 문제를 프롬프트 1회 일괄 수집 지침으로 개선.
     - `RecommendBooksTool` 및 오케스트레이터 기본 추천 권수를 `count=2`로 고정하여 화면 스크롤 없이 2권이 2초 만에 깔끔하게 출력되도록 튜닝.
  4. **프론트엔드 단계별 점진적 진행 UX(Progressive Stages) 및 UI 개선**:
     - 질문 전송 후 0초(사서 상담) ➔ 2.5초(도서 검색) ➔ 5.5초(서재 정리)의 단계별 실시간 상태 메시지 연출로 대기 체감 시간 0초화.
     - 사서 머리 위 말풍선(`LibrarianCursor.jsx`)에서 사서의 첫마디가 휙 바뀌지 않고 안정적으로 유지되도록 개선.
     - `MarkdownRenderer.jsx` 및 `RegisterBook.jsx`의 제목/텍스트를 왼쪽 정렬(`textAlign: 'left'`)로 통일.
  5. **사서 서버(backend-librarian) 최종 페르소나 및 특화 영역 완벽 동기화**:
     - 블루(고양이 사서): 🔍 미스터리/추리/탐정/스릴러 특화 + 감성/에세이. 비즈니스/경영/투자 질문 또는 "슈빌" 호칭 시 `switch_to: stork` 제안.
     - 슈빌(황새 사서): 📈 비즈니스/경영/경제/투자/스타트업 특화 + SF/과학. 미스터리/추리/감성 질문 또는 "블루" 호칭 시 `switch_to: cat` 제안.
     - `ChatResponse`의 `signals` 및 스트리밍 `X-Signals` 헤더 배선 완료.
  6. **사서별(블루 ⇄ 슈빌) 동적 전용 시스템 프롬프트 및 UI/말풍선 일체화 완성**:
     - `src/discovery/domain/orchestrator/agent.py`: `CAT_ORCHESTRATOR_PROMPT`와 `STORK_ORCHESTRATOR_PROMPT`로 분리하여 활성 사서 ID에 따라 전용 프롬프트 주입.
     - 슈빌: 시그니처 추임새 '두둥!', 공손체, 비즈니스 특화, 고양이 말투 100% 차단.
     - 블루: 친근한 반말, 문장 끝 `~다냥 🐾`, 미스터리 특화.
     - `src/discovery/domain/librarian/agent.py` & `recommend_tool.py`: 추천 에이전트 도서 소개 이유 생성 시에도 사서별 어조 분기 적용.
     - `LibrarianCursor.jsx`: 말풍선 텍스트에 슈빌 전용 문구(`✨ 두둥! 추천 도서 N권을 선별했습니다 🪶`) 지원.
     - `LibrarianChat.jsx`: 사서 스위칭 제안 시 도서 등록 버튼 비활성화, 스위칭 버튼 클릭 시 직전 질문으로 슈빌 자동 재질의(`auto-submit`) 구현.
  7. **슈빌 시그니처 '두둥!' 로딩 문구 반영 및 프리미엄 도서 카드(BookCardView) UI 미려화**:
     - `LibrarianChat.jsx`: `🪿 두둥! 슈빌 사서가 전문 분야의 깊이 있는 명저를 선별하고 있습니다... 🪶`로 로딩 텍스트에 시그니처 반영.
     - `MarkdownRenderer.jsx`: `### 📖` 블록을 파싱하여 도서 제목 뱃지 + 저자/쪽수 메타 칩 + 추천 이유 은은한 하이라이트 박스로 구성된 프리미엄 북 카드 UI 컴포넌트(`BookCardView`)로 리팩토링.
     - `librarian_tool.py`: 로컬 사서 fallback 멘트에도 슈빌의 '두둥!' 반영.
  8. **검증**:
     - 정적 분석(`ruff`, `mypy`) 100% 통과, 단위 테스트 112건 전체 통과.

### 다음 세션이 할 일
1. `PR #14` (`develop` 대상) 코드 리뷰 및 머지.
2. dev 환경(K8s) 배포 후 클러스터 내부 `backend-librarian:8000` 통신 및 프론트엔드 연동 확인.
3. [제안] 단일 오케스트레이터 기반 올인원 독서 비서 Phase 0~4 착수.


## 2026-08-28 — CLIAR-152 올인원 독서 비서 (내 서재 CRUD API 연동 및 복합 의도 오케스트레이션) 완료
- 브랜치: `CLIAR-152-Unified-Agent-Assistant` (`develop`에서 분기).
- 사용자가 프론트엔드에서 수동 모드 분기 없이 단일 자연어 입력창으로 내 서재 검색, 외부 도서 추천, 사서 상담, 복합 의도(서재 기반 추천)를 원스톱으로 사용할 수 있도록 아키텍처를 확장했다:
  - Task 1: `core/config.py` 및 `.env.example`에 `library_api_url`(`http://k8s-dpybbook-backendb-d17a725d36-1113312703.ap-northeast-2.elb.amazonaws.com`), `library_http_timeout_seconds: 10.0` 분리 추가. `domain/orchestrator/library_response.py`에 `LibraryBookItem`, `LibraryBooksResponse` Pydantic DTO 정의.
  - Task 2: `domain/orchestrator/tools/library_tool.py` 신설 (`SearchMyLibraryTool`). `GET /api/v1/library/books` API 호출, `auth_token` 클로저 주입(IDOR 원천 방지), 제목/저자/장르 부분일치 및 독서상태(`readingStatus`) 필터링, LLM 친화적 정형 텍스트(`format_books_for_llm`) 변환 구현.
  - Task 3: `api/v1/routers/chat.py`에서 `Authorization: Bearer <token>` 헤더를 추출하여 `OrchestratorService.chat` 및 `stream_chat`에 전달. `api/deps.py`에 `get_search_my_library_tool` 배선.
  - Task 4: `domain/orchestrator/agent.py`의 `CAT_ORCHESTRATOR_PROMPT` 및 `STORK_ORCHESTRATOR_PROMPT`에 `search_my_library` 도구 분기 규칙(단순 서재 조회 ➔ 서재 도구, 복합 추천 ➔ 서재 도구 ➔ 추천 도구 연쇄) 주입.
  - Task 5: `extract_fallback_text` 결합 안전장치를 화이트리스트(`has_book_card = "### 📖" in tool_result`)로 제한하여 서재 원시 텍스트 중복 노출 방지. `test_library_tool.py`, `test_chat_router.py`, `test_orchestrator_service.py`, `test_orchestrator_routing.py` 단위 테스트 갱신 및 신설. 정적 분석(`ruff`, `mypy`) 100% 통과, 단위 테스트 121건 전체 통과.
  - Task 6: `docs/api/decisions/0004-my-library-integration.md` (ADR 0004) 작성 및 `docs/api/openapi.yaml`, `.harness/ARCHITECTURE.md`, `.harness/STATE.md`, `.harness/DECISIONS.md`, `.harness/PLAN.md` 갱신.
- 커밋·push 완료 (`bc9db6d`, `git push -u origin CLIAR-152-Unified-Agent-Assistant`).

### 다음 세션이 할 일
1. 프론트엔드(`my-reading-room`) 단일 챗 UI에서 `Authorization` 헤더 전송 및 서재 검색 / 추천 / 복합 대화 E2E 테스트.
2. K8s dev 환경 배포 후 통신 검증.


## 2026-08-28 — Bedrock 성능 고도화 3단계(관측 ➔ 직결 스트리밍 ➔ 인프라 최적화) 계획 수립
- `CLIAR-152` 커밋 및 원격 푸시 완료 상태 확인.
- 워킹 트리에 남아 있는 `src/discovery/domain/librarian/agent.py`의 도서 공식 풀네임/시리즈명 표기 지침 보강 수정사항 확인.
- Bedrock 관점의 성능 고도화 작업 3가지를 "관측(Observability) ➔ 아키텍처 개선(직결 스트리밍) ➔ 인프라 최적화(AWS Bedrock Latency-Optimized Inference)"의 계층적 스토리라인으로 정리하여 `.harness/PLAN.md`에 확정 계획으로 수립:
  - **Phase 1 (Observability)**: TTFT, 오케스트레이터 분류 시간, 도구 I/O 및 내부 LLM 추론 시간 구간별 계측 로거 구축 및 베이스라인 측정.
  - **Phase 2 (Direct Streaming Pipeline)**: 하위 에이전트 생성 스트림을 클라이언트로 즉시 직결 바이패스하여 2중 버퍼링 및 재포장 추론 턴 제거 (체감 2~3초 단축).
  - **Phase 3 (Latency-Optimized Inference)**: AWS Bedrock의 Latency-Optimized Routing / Inference Profile 지원 현황(리전/모델) 조사 및 가능 시 적용.
- 캐싱(이미 적용됨), Structured Output(별도 트랙), 병렬 도구(추후 도구 증가 시 검토)는 백로그로 명확히 분리.

### 다음 세션이 할 일
1. 새 티켓 브랜치 생성 (예: `CLIAR-153-Agent-Performance-Optimization` 등) 및 `agent.py` 잔여 수정사항 반영.
2. `.harness/PLAN.md`의 Phase 1 (구간별 레이턴시 계측 로거 및 베이스라인 실측)부터 착수.
3. Phase 1 실측 데이터를 바탕으로 Phase 2 직결 스트리밍 파이프라인 구현 및 비교 검증.


## 2026-08-29 — 도서 표준 장르 분류 API의 ISBN 필드 지원 및 LLM 식별 강화 완료
- 도서 OCR 및 메인 API 서버(`backend-book`)의 `GET /api/v1/books/search`가 고유 식별자인 `isbn` 기반 검색으로 개편됨에 따라, `backend-discovery`의 도서 표준 장르 분류 API(`POST /api/v1/classify-genre`)에서도 `isbn`을 수신하여 LLM 프롬프트에 도서 식별 단서로 제공하도록 지원을 완료했다:
  - Task 1: `docs/api/openapi.yaml` 계약 갱신 및 `src/discovery/api/schemas/genre.py`의 `BookClassificationRequest`에 `isbn: str = Field(default="", ...)` 선택 필드 추가.
  - Task 2: `src/discovery/domain/genre/classifier.py`의 `GENRE_CLASSIFIER_SYSTEM_PROMPT` 및 `build_classification_prompt`에 `isbn` 파라미터 반영 (ISBN이 제공되면 도서 고유 식별자로 최우선 분석, 미제공 시 기존 title/author/raw_category로 fallback). `src/discovery/application/genre_classifier_service.py`의 `classify_genre`에 `isbn` 전달 배선.
  - Task 3: `tests/unit/test_genre_classifier.py` 및 `tests/unit/test_genre_router.py`에 ISBN 포함/미포함 단위 테스트 추가, 정적 분석(`ruff`, `mypy`) 100% 통과 및 단위 테스트 123건 전체 통과.
  - Task 4: `docs/api/decisions/0002-book-genre-classification.md` (ADR 0002), `.harness/STATE.md`, `.harness/ARCHITECTURE.md`, `.harness/PLAN.md` 문서 동기화 완료.

### 다음 세션이 할 일
1. API 서버(`backend-book`) 및 OCR 파이프라인에서 `POST /api/v1/classify-genre`로 `isbn`을 포함한 요청 전송 및 장르 매핑 검증.
2. 커밋/push 요청 시 진행.
3. Bedrock 성능 고도화 3단계 착수.


## 2026-08-30 — 에이전트 서비스 활용 유도(CTA) 및 과잉 도구/장문 줄거리 방어 가드레일 보강 완료
- 사용자가 에이전트와의 대화 속에서 자연스럽게 책 상세 확인, 독서 진행률 기록, 한 줄 감상 메모 등 서비스 기능을 활용할 수 있도록 유도(CTA)를 추가하고, 불필요한 웹 검색 과잉 호출 및 장문 줄거리 생성을 원천 차단하는 가드레일을 구축했다:
  - Task 1: `src/discovery/domain/orchestrator/agent.py`의 `CAT_ORCHESTRATOR_PROMPT` 및 `STORK_ORCHESTRATOR_PROMPT`에 (1) 단순 서재 조회 시 `recommend_books` 및 웹 검색 도구 호출 완벽 차단, (2) 묻지 않은 줄거리 나열 금지 및 독서 상태별(읽는 중: 진행률/요약 질문, 완독: 감상 기록, 멈춤: 요약 제안) 1~2줄 가벼운 CTA 템플릿 주입.
  - Task 2: `src/discovery/domain/librarian/agent.py`의 `CAT_LIBRARIAN_PROMPT` 및 `STORK_LIBRARIAN_PROMPT`의 `- **추천 이유**:` 규칙에 *“전체 줄거리 나열/스포일러 엄격 금지, 핵심 매력과 추천 이유만 2~3문장 이내 압축 작성”* 가드레일 추가.
  - Task 3: `tests/unit/test_orchestrator_agent.py` 및 `tests/unit/test_librarian_agent.py` 단위 테스트 갱신, 정적 분석(`ruff`, `mypy`) 100% 통과 및 단위 테스트 123건 전체 통과.
  - Task 4: `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

### 다음 세션이 할 일
1. K8s 파드 Bedrock 호출 IAM/Credentials 설정 확인 후 배포 환경 E2E 테스트.
2. 사용자 요청 시 커밋/push 진행.
3. Bedrock 성능 고도화 3단계(관측 ➔ 직결 스트리밍 ➔ 인프라 최적화) 착수.


## 2026-08-31 — 프론트엔드 연동 지원: CORS expose_headers 확장 및 ChatRequest 2000자 상향 완료 [CLIAR-184]
- 프론트엔드(`my-reading-room`)와의 실연동 과정에서 확인된 액션 아이템 2건을 수정 및 배포 준비 완료했다:
  - Task 1: `src/discovery/api/schemas/chat.py`의 `ChatRequest.message` 필드 `max_length`를 1000자에서 2000자로 상향하고, `docs/api/openapi.yaml` 계약(message maxLength: 2000, 200 응답 헤더 `X-Signals`, `X-Switch-To`)을 동기화.
  - Task 2: `src/discovery/main.py`의 CORS `expose_headers`에 `["X-Session-Id", "X-Signals", "X-Switch-To"]`를 추가하여 브라우저에서 날씨 뱃지/신호 및 사서 전환 헤더를 정상 수신하도록 수정.
  - Task 3: `tests/unit/test_chat_router.py`에 2000자 정상 처리, 2001자 거부(422) 및 CORS `access-control-expose-headers` 검증 테스트 추가. 정적 분석(`ruff`, `mypy`) 100% 통과 및 단위 테스트 126건 + Redis 통합 테스트 16건 전체 통과.
  - Task 4: `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

### 다음 세션이 할 일
1. develop 머지 후 프론트엔드 배포 환경에서 날씨 뱃지, 사서 전환 버튼, 2000자 입력창 E2E 연동 검증.


## 2026-08-31 — AWS Bedrock Claude Sonnet 5 글로벌 추론 프로필 적용 및 dev 배포 환경 Bedrock 활성화 [CLIAR-189]
- 교육 계정의 Bedrock 접근 권한 승인에 따라, discovery 오케스트레이터 및 도서 추천 에이전트의 모델을 최신 Claude Sonnet 5 글로벌 크로스리전 추론 프로필(`global.anthropic.claude-sonnet-5`)로 적용하고 dev K8s 환경을 실 Bedrock으로 전환했다:
  - Task 1: `src/discovery/core/config.py` 및 `k8s/base/configmap.yaml`의 `orchestrator_model_id`, `librarian_model_id`를 `global.anthropic.claude-sonnet-5`로 갱신.
  - Task 2: `k8s/overlays/dev/configmap-patch.yaml`의 `LLM_PROVIDER`를 `"mock"` ➔ `"bedrock"`으로 수정하여 실제 Bedrock LLM 실시간 추론 활성화.
  - Task 3: `tests/unit/test_orchestrator_agent.py`, `tests/unit/test_librarian_agent.py`의 Sonnet 5 모델 ID 팩토리 검증 테스트 갱신. 정적 분석(`ruff`, `mypy`) 100% 통과 및 단위 테스트 126건 + Redis 통합 테스트 16건 전체 통과.
  - Task 4: `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

## 2026-08-31 — 스트리밍 초기 블로킹 제거(Fast TTFB) 및 사서 연동 장애 격리 고도화 완료 [CLIAR-194]
- 브랜치: `CLIAR-194-Streaming-Fast-TTFB-NonBlocking-Meta` (`origin/develop`에서 분기).
- 스트리밍 대화 요청(`POST /api/v1/chat?stream=true`) 시, 사전 메타데이터(`get_initial_meta`) 조회로 인해 사서 서버(`backend-librarian`)가 느려지거나 통신 장애가 발생했을 때 전체 스트리밍 개시가 수십 초간 블로킹되어 ALB 30초 타임아웃(`ERR_HTTP2_PROTOCOL_ERROR`)이 발생하던 문제를 해결했다:
  - Task 1: `src/discovery/core/config.py` 및 `k8s/base/configmap.yaml`에 `initial_meta_timeout_seconds: float = 1.5` 필드 및 환경 변수 추가.
  - Task 2: `src/discovery/application/orchestrator_service.py`의 `get_initial_meta`에서 사서 서버 호출을 `asyncio.wait_for(..., timeout=self._settings.initial_meta_timeout_seconds)`로 감싸고, 타임아웃 발생 시 `[INITIAL_META_TIMEOUT]` 로깅 후 `(None, None)`을 즉시 반환하여 브라우저에 0.1초 이내 스트리밍 응답(`StreamingResponse`)이 열리도록 보장.
  - Task 3: `tests/unit/test_orchestrator_service.py`에 `get_initial_meta` 1.5초 타임아웃 및 예외 처리 비동기 단위 테스트 3건 추가. 정적 분석(`ruff`, `mypy`) 및 단위 테스트 133건 100% 통과.
  - Task 4: `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

### 다음 세션이 할 일
1. `CLIAR-194` 커밋, push 및 `develop` 대상 PR 생성.
2. 배포 후 프론트엔드에서 스트리밍 대화 요청 시 TTFB 즉각 응답 및 30초 타임아웃 해소 확인.


## 2026-08-31 — 내 서재 도서 조회 API(GET /api/v1/library/books) Spring Data Page 및 전방위 규격 호환성 강화 완료 [CLIAR-195]
- 브랜치: `CLIAR-195-Library-API-Page-Compatibility` (`origin/develop`에서 분기)
- 프론트엔드와 `backend-book` 간의 서재 조회 규격(Spring Data JPA Page `content`, `page=0&size=100`)을 Discovery의 `SearchMyLibraryTool` 및 `LibraryBooksResponse` DTO에 100% 호환되도록 보강했다:
  - Task 1: `src/discovery/domain/orchestrator/library_response.py`에 `@model_validator(mode="before")`를 추가하여 Spring Page 표준 `content` 키, `data` 래핑 구조(`data.content`, `data.books`, `data.items`), 순수 배열(`[...]`), `items` 키 등 어떤 규격의 응답이 오더라도 `books: list[LibraryBookItem]`으로 자동 변환되도록 다형성 파서를 구축하고, `LibraryBookItem`에 `extra="ignore"` 및 소수점 진행률(`progress: float`, 예: `88.0165...`)을 정수(`88`)로 반올림 변환하는 `field_validator` 추가.
  - Task 2: `src/discovery/domain/orchestrator/tools/library_tool.py`의 `params`를 프론트엔드 규격과 동일한 `{"page": 0, "size": 100}`으로 정렬하고, 호출 URL, 상태 코드, 파싱된 도서 수에 대한 상세 로깅 추가.
  - Task 3: `tests/unit/test_library_tool.py`에 Spring Page `content` 응답, 순수 배열 응답, `data` 래핑 응답, `page=0&size=100` 파라미터 전달 및 소수점 progress 반올림 단위 테스트 4건 추가.
  - Task 4: 정적 분석(`ruff`, `mypy`) 100% 통과 및 단위 테스트 137건 전체 통과. `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

## 2026-08-31 — 내 서재 도서 구조화 데이터(library_books) 응답 및 "책 열기" 연동 계약 구축 완료 [CLIAR-196]
- 브랜치: `CLIAR-196-Library-Books-Structured-Response` (`origin/develop`에서 분기)
- 서재 조회 시 마크다운 텍스트 파싱에 의존하지 않고, 구조화된 도서 DTO(`LibraryBookCard`) 및 응답 필드(`library_books`), 스트리밍 헤더(`X-Library-Books`)를 통해 클라이언트에 `book_id` 및 메타데이터를 직접 전달하여 프론트엔드가 '책 열기' UI를 완벽하게 구현할 수 있도록 계약을 수립했다:
  - Task 1: `docs/api/openapi.yaml` 계약 갱신, `src/discovery/api/schemas/chat.py`에 클라이언트 전용 `LibraryBookCard` 모델(`book_id`, `title`, `author`, `reading_status`, `progress`) 정의, `ChatResponse`에 `library_books: list[LibraryBookCard] | None` 추가 및 `src/discovery/main.py` CORS `expose_headers`에 `"X-Library-Books"` 등록.
  - Task 2: `src/discovery/domain/orchestrator/tools/library_tool.py`의 `format_books_for_llm`에는 `book_id`를 노출하지 않아 LLM 대화문 오염을 방지하고, `SearchMyLibraryTool.as_tool`에 `on_books_fetched` 콜백을 배선하여 도서 식별자 원본 객체를 서비스 레이어로 전달.
  - Task 3: `src/discovery/application/orchestrator_service.py`의 `_build_agent`, `chat`, `stream_chat`에서 서재 도구 실행 시 수집된 도서 목록을 `list[LibraryBookCard]`로 매핑하여 `ChatResponse.library_books`로 방출.
  - Task 4: `src/discovery/domain/orchestrator/agent.py`의 `CAT_ORCHESTRATOR_PROMPT` 및 `STORK_ORCHESTRATOR_PROMPT`의 서재 안내 지침을 "콜론/줄바꿈/볼드체 나열 금지, 자연스러운 한두 문장 대화문 서술"로 정돈하여 프론트엔드 파서 오작동(엉뚱한 등록 버튼 3개 생성)을 원천 차단.
  - Task 5: `tests/unit/test_chat_router.py`, `tests/unit/test_orchestrator_service.py`, `tests/unit/test_library_tool.py`, `tests/unit/test_orchestrator_routing.py` 단위 테스트 갱신 및 신설. 복합 추천 시 `library_books`가 포함되는 1차 알려진 동작 명시 회귀 테스트 추가. 정적 분석(`ruff`, `mypy`) 및 단위 테스트 139건 100% 통과.
  - Task 6: `docs/api/decisions/0005-library-books-card-response.md` (ADR 0005) 작성 및 `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

### 다음 세션이 할 일
1. `CLIAR-196` PR(#27) 머지 완료 확인.
2. `CLIAR-208` 커밋, push 및 `develop` 대상 PR 생성.

## 2026-09-01 — 사서 로컬 페르소나 fallback 의도 게이트 고도화 및 하드코딩 응답 제거 [CLIAR-208]
- 브랜치: `CLIAR-208-Dynamic-Persona-Fallback` (`origin/develop`에서 분기)
- 사용자가 단순 인사, 일상 대화, 서재 질문 등을 건넸을 때 로컬 페르소나 fallback 엔진(`evaluate_local_persona_response`)이 무조건 도서 추천 멘트를 반환하거나 키워드 단독 매칭으로 엉뚱하게 `switch_to`를 발동시키던 문제와 오케스트레이터 프롬프트 내 판박이 CTA 복붙(앵무새 현상) 문제를 해결했다:
  - Task 1: `src/discovery/domain/orchestrator/tools/librarian_tool.py`의 `evaluate_local_persona_response`에 우선순위 의도 게이트(1단계: 인사/정체성 최우선 필터 ➔ 2단계: 상대 사서 직접 호출 `is_call_other_librarian` ➔ 3단계: 추천 의도 `has_rec_intent` AND 상대 도메인 키워드 결합 ➔ 4단계: 명시적 추천 요청 ➔ 5단계: 비추천 일반 대화/감정)를 구축하여 도서 추천 멘트 남발을 원천 차단.
  - Task 2: 호칭 키워드셋(`STORK_CALL_KEYWORDS`, `CAT_CALL_KEYWORDS`)과 장르 키워드셋(`STORK_GENRE_KEYWORDS`, `CAT_GENRE_KEYWORDS`)을 물리적으로 분리하고 스코어링 없는 결정론적 Boolean 조건식 결합(`is_calling_other or (has_rec_intent and has_domain)`) 적용.
  - Task 3: `src/discovery/domain/orchestrator/agent.py`의 `CAT_ORCHESTRATOR_PROMPT` 및 `STORK_ORCHESTRATOR_PROMPT`에서 고정된 문장 텍스트 예시(few-shot 복붙 유발)를 전면 제거하고 상황별 유연한 소통 가이드라인으로 개선.
  - Task 4: `tests/unit/test_librarian_tool.py`에 인사/호칭 충돌 방어, 동일 사서 호칭 방어, 상대 사서 단독 호출, 일상 대화 방어, 조회 vs 추천 대조 단위 테스트 4건 추가 및 `tests/unit/test_orchestrator_agent.py`에 프롬프트 내 고정 예시 부재 검증 추가. 단위 테스트 143건 및 정적 분석(`ruff`, `mypy`) 100% 통과.
  - Task 5: `ARCHITECTURE.md`, `.harness/STATE.md`, `.harness/PLAN.md`, `.harness/HANDOFF.md` 문서 동기화 완료.

### 다음 세션이 할 일
1. `CLIAR-208` 커밋 생성, push 및 `develop` 대상 PR 생성.
2. 배포 후 프론트엔드에서 단순 인사("안녕", "블루야 안녕"), 일상 대화("돈 아끼는 법 알려줘"), 서재 조회 시 추천 멘트 미포함 및 자연스러운 대화 E2E 확인.
3. Bedrock 실호출 시 서재 응답의 CTA가 책 내용에 맞게 유연하게 생성되는지 샘플링 확인.












