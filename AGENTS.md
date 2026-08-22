## 하네스: 크로스 툴 작업 연속성

**세션 시작 시 반드시 먼저 읽을 것 (이 순서로):**

1. `.harness/HANDOFF.md` — 직전 세션이 어디서 멈췄는지
2. `.harness/STATE.md` — 지금까지 무엇이 완료되었는지
3. `.harness/ARCHITECTURE.md` — 기술 스택/구조 요약 (코드베이스 재탐색 최소화)
4. `.harness/PLAN.md` — 제안·확정·진행 중인 계획
5. 필요 시 `.harness/DECISIONS.md`(과거 결정 이유), `.harness/BACKLOG.md`(미해결 항목)

**문서별 책임 (중복 기록 금지 — 아래 표에 없는 문서에는 해당 내용을 쓰지 않는다):**

| 문서 | 담는 내용 | 담지 않는 내용 |
| --- | --- | --- |
| `HANDOFF.md` | 세션마다 무엇을 했는지 (append-only 서술형 로그) | 단계별 완료 요약(STATE 몫), 결정 이유(DECISIONS 몫) |
| `STATE.md` | 지금까지 끝난 것의 단계 단위 요약 스냅샷 | 세션별 서술(HANDOFF 몫). 이슈 하나하나를 로그처럼 쌓지 않는다 — 단계가 끝나면 그 단계 한 줄로 갱신 |
| `ARCHITECTURE.md` | 지금의 기술 스택/폴더 구조/컨벤션 (현재 상태) | 왜 그렇게 정했는지(DECISIONS 몫), 진행 상황(STATE 몫) |
| `DECISIONS.md` | 결정 내용과 이유의 역사(append-only) | 구현 여부/진행 상황(STATE 몫) |
| `PLAN.md` | 아직 안 끝난 계획과 체크리스트만 | 완료된 항목(체크만 남기지 말고 STATE로 옮긴 뒤 제거) |
| `BACKLOG.md` | 지금 하지 않지만 나중에 할 것(버그·기술부채·아이디어) | 진행 중인 계획(PLAN 몫) |

API wire 계약과 계약 결정은 `.harness`가 아니라 `docs/api/openapi.yaml`, `docs/api/README.md`, `docs/api/decisions/`가 소유한다. `.harness`는 이 산출물을 복제하지 않고 참조한다.

**작업 워크플로우 (필수):**

- 새로운 기능/변경 요청을 받으면, 바로 구현하지 말고 `.harness/PLAN.md`에 계획 초안을 작성한다.
- 사용자에게 계획을 제시하고 피드백을 받아 반영하는 과정을 반복한다.
- 사용자가 명시적으로 컨펌하면 계획을 확정 상태로 바꾸고 구현을 시작한다.
- 다음은 계획 절차 없이 바로 수행한다: 설명·조사·코드 리뷰처럼 파일을 변경하지 않는 요청, 오탈자나 명백한 단순 수정(수정 전 무엇을 바꾸는지 한 줄로 알린다).
- `PLAN.md` 단계별 체크리스트 항목은 하나씩 구현이 끝날 때마다 즉시 `.harness/STATE.md`에 반영하고, 그 항목을 `PLAN.md`에서 제거한다. `STATE.md`에는 위 표대로 단계 단위 한 줄 요약만 남기고 세션 서술은 남기지 않는다.
- 구현 완료 후 `.harness/STATE.md`를 갱신한다.
- 세션을 종료하거나 작업을 중단할 때 `.harness/HANDOFF.md`에 다음 세션을 위한 인수인계를 남긴다.
- 아키텍처/워크플로우에 대한 중요한 결정을 내리면 `.harness/DECISIONS.md` 표의 최상단에 이유와 함께 기록해 최신 결정이 위에 오도록 유지한다.

**트리거:** 이 프로젝트에서의 모든 작업 요청에 위 워크플로우를 적용하라. 단순 질문(코드 설명 등)은 하네스 절차 없이 바로 응답 가능.

## 하네스: 변경 산출물 동기화

**목표:** 한 변경이 여러 산출물에 걸쳐 있을 때, 코드나 정책을 고치면서 관련 문서를 빠뜨리지 않는다.

**단일 소유권:**

| 정보 | 소유 산출물 |
| --- | --- |
| 개발 하네스 워크플로우, DB·테스트·브랜치 정책 | `AGENTS.md` |
| 크로스 툴 인수인계·진행 상황·아키텍처 현황·계획·결정·백로그 | `.harness/*.md` |
| API wire 계약 | `docs/api/openapi.yaml` |
| API 문서 탐색·사용법 | `docs/api/README.md` |
| API 계약 결정과 근거 | `docs/api/decisions/` |
| 저장소 진입점, 커밋 컨벤션 | 루트 `README.md` |

**변경 시 함께 갱신할 것:**

- **DB·테스트·브랜치 정책 변경** (`AGENTS.md` 수정): `.harness/ARCHITECTURE.md`의 관련 서술, `.harness/DECISIONS.md`에 결정 이유 추가
- **기술 스택·패키지 구조 변경**: `.harness/ARCHITECTURE.md`, 파이썬 의존성 파일 (`pyproject.toml`, `poetry.lock` 또는 `uv.lock`), 관련 테스트 설정
- **API endpoint·요청/응답 스키마 변경**: `docs/api/openapi.yaml`을 먼저 수정하고, 호환성이 깨지거나 정책 근거가 필요하면 `docs/api/decisions/`에 ADR 추가, Router·Schema(Pydantic)·계약 테스트를 함께 갱신
- **완료된 계획 항목**: `.harness/PLAN.md`에서 제거하고 `.harness/STATE.md`에 단계 한 줄로 반영
- **README.md에 링크·안내가 걸린 파일을 이동·삭제·이름변경**: `README.md`의 해당 링크를 같은 작업에서 수정하거나 제거

## 하네스: DB 정책

**목표:** 서비스별 DB 소유권과 로컬·테스트·운영에서 사용할 DB 엔진을 고정한다.

- 현재 RDB 없음. `ChatSessionStore`(Redis)만 사용한다. 로컬 개발 환경의 Redis는
  Docker(또는 Docker Compose)로 실행한다. 운영 접속 정보는 환경 변수(`.env`)나
  비밀값으로 주입하고 코드나 설정 파일에 기본값을 하드코딩하지 않는다.

## 하네스: 테스트 및 정적 분석 실행 정책

- 이 저장소는 루트에서 단일 Python 패키지로 관리된다. 모든 명령은 가상환경이 활성화된 상태에서 저장소 루트를 기준으로 실행한다.
- 구현·수정 후 **기본 검증**은 **린트/타입 체크(`ruff`, `mypy` 등) 통과 후, 단위 테스트만 실행**한다 (`pytest -m "not integration"`).
- **TDD로 통합 테스트를 작성·수정하는 작업** 중에는 해당 통합 테스트를 반드시 실행한다.
- **통합 테스트 전체 스위트**(`pytest -m integration`)와 **전체 검증**(`pytest`)은 사용자가 명시적으로 요청했거나 CI에서 실행한다.
- **CI 전체 검증(Check):** CI 파이프라인은 정적 분석(Linter/Type Checker)과 `test`, `integration`을 모두 실행해 파이썬의 동적 타이핑으로 인한 런타임 에러와 Redis 연동 검증이 누락되지 않게 한다.
- 단위 테스트: Domain/Application 로직(pytest-mock 사용) 등 실제 인프라를 사용하지 않는 테스트.
- 통합 테스트: Redis Testcontainers 기반, 실제 Redis와 FastAPI 라우팅을 통과하는 테스트.

## 하네스: 통합 테스트 구조

**목표:** Redis 실제 동작 검증은 유지하면서 통합 테스트 기동 비용을 줄이고, 비동기 환경의 안정성을 확보한다.

| 분리 기준 | Pytest Fixture/설정 | 용도 |
| --- | --- | --- |
| `E2E / API 계층 테스트` | `client` (httpx.AsyncClient) | 앱 전체 기동 검증, 의존성 주입(DI) 오버라이드, API 스택 전체 |
| `Redis 연동 테스트` | 개별 테스트 파일 내 Testcontainers 픽스처 (예: `redis_container`) | 실제 Redis 컨테이너로 `ChatSessionStore` 등 동작 검증 |

- **비동기 테스트:** FastAPI와 Redis 비동기 클라이언트(redis.asyncio)를 사용하는 경우, 모든 I/O 바운드 테스트는 `pytest-asyncio` 마커(`@pytest.mark.asyncio`)를 사용하고, API 테스트에는 `TestClient` 대신 비동기 요청이 가능한 `httpx.AsyncClient`를 사용한다.
- **데이터 격리:** Redis를 쓰는 통합 테스트는 테스트가 끝나면 사용한 키를 정리(`flushall` 또는 개별 삭제)해 격리를 보장한다.

## 하네스: 테스트 작성 원칙 (결과 검증 우선)

**목표:** 테스트가 내부 구현이 아니라 관찰 가능한 최종 결과(반환값·상태·예외)를 검증하게 하여, 테스트 리팩토링 내구성을 강화한다.

- 단위 테스트는 반환값, 변경된 상태, 발생한 예외를 검증하는 것을 기본으로 한다. Mock(`pytest-mock`의 `mocker`)의 `assert_called_once()` 등은 "부작용이 실행됐는지" 확인에만 제한적으로 쓴다.
- Mock으로는 결과 자체를 관찰할 수 없는 경우(동시성 등)는 실제 인프라(Testcontainers)를 쓰는 통합 테스트로 결과를 검증한다.
- 제어 불가능한 값(현재 시각, UUID 생성 등)은 로직 내부에서 직접 호출하지 않고 파라미터나 의존성 주입(Dependency Injection)으로 받아 결정론적으로 동작하게 한다.
- 도메인 객체(Entity, Model)는 계산 후 상태 변경/값 반환까지만 책임지고, DB 커밋이나 외부 API 호출 같은 부작용은 바깥 계층(Service/Usecase)이 담당한다.
- 쿼리에 비결정적 함수(`datetime.now()` 등)나 하드코딩된 조건을 넣지 않고 파라미터로 받는다. 

## 하네스: ORM(SQLAlchemy) 조회 및 DTO 직렬화 최적화

- **N+1 문제 방지 (Eager Loading):** 연관관계 조회에서 N+1 문제가 발생하면 SQLAlchemy의 명시적 로딩을 사용한다.
  - To-One (다대일, 일대일) 관계는 `joinedload()`를 사용한다.
  - To-Many (일대다, 다대다) 관계는 DB 페이징 등 중복 행 문제를 피하기 위해 `selectinload()`를 사용한다.
- **페이징 쿼리 제한:** 페이징 목록 쿼리에서는 To-Many 컬렉션에 대한 `joinedload`를 절대 사용하지 않는다.
- **API 응답 스키마 분리:** 응답 스키마(Pydantic)는 목록용과 상세용으로 분리한다. 목록 스키마는 페이징 쿼리가 To-One 연관관계만으로 완성되도록 설계한다.
- **Pydantic 직렬화 (영속성 분리):** ORM 객체는 비즈니스/프레젠테이션 계층으로 넘어갈 때 반드시 Pydantic Schema로 직렬화(Serialization)되어야 한다. 
  - 이를 위해 반환 스키마에는 `model_config = ConfigDict(from_attributes=True)`를 명시한다.
  - **[중요]** 파이썬의 `AsyncSession` 특성상 밖에서 Lazy 속성에 접근하면 즉시 에러가 발생하므로, 비동기 세션 컨텍스트가 닫히기 전에 Pydantic 모델로 파싱(Parsing)을 완전히 완료하여 `MissingGreenlet` 예외를 원천 차단한다.

## 하네스: 브랜치·커밋·병합 전략

- 원격 저장소는 `origin` (`https://github.com/dont-paw-get/backend-discovery.git`)이며 `main`과 `develop`을 갖는다.
- 작업 브랜치는 `develop`에서 분기하고 이름은 `{티켓번호}-{설명}` 형식을 사용한다 (예: `CLIAR-9-Steering-Scaffolding`). `feature/...` 형식은 사용하지 않는다.
- 현재 브랜치가 진행 중인 작업과 다른 티켓이면, 구현 시작 전에 해당 티켓 번호로 새 브랜치를 `develop`에서 생성하고 전환한다. 이미 해당 티켓 브랜치에 있다면 새 브랜치를 만들지 않는다.
- 문서·설정 전용 작업도 코드 변경과 동일하게 티켓 브랜치에서 진행한다. main에 직접 커밋하는 예외는 두지 않는다.
- 커밋 메시지 컨벤션은 저장소 루트 `README.md`(`CLIAR-20`)를 그대로 따른다.
  - `<타입>[적용 범위(선택)]: <제목>` 구조. 타입은 영어(`feat`, `fix`, `docs`, `style`, `refactor`, `test`, `chore`), 제목/본문은 한국어.
  - 제목은 명사형 어미로 끝내고 50자 이내, 마침표 없음.
  - scope는 작업한 도메인(예: `curation`, `db`)을 명시하면 이력 추적에 유리하다.
  - 제목 또는 본문에 관련 티켓 번호를 `[CLIAR-9]`처럼 표기한다 (기존 이력 패턴).
- 커밋은 사용자가 명시적으로 요청했을 때만 생성한다. 관련 파일을 골라 stage하고, `git add .`/`git add -A`는 피한다.
- 한 티켓 브랜치에서 작업이 끝나면 PR을 `develop`으로 생성할 수 있지만, PR 생성과 push는 사용자가 명시적으로 요청했을 때만 수행한다.
- 브랜치 병합과 삭제는 자동으로 수행하지 않는다. PR 병합은 사용자가 직접 하거나, 사용자가 명시적으로 요청했을 때만 수행한다. `develop → main` 릴리스 병합도 동일하다.
- 강제 push, `reset --hard`, `clean -fd`, `branch -D` 등 destructive 작업은 사용자의 명시적 허락 없이 수행하지 않는다.

## Git 작업 정책

- commit: Task 단위로 나누어 작성, 형식 `[CLIAR-XX]` 태그 필수 (위 커밋 메시지 컨벤션과 함께 적용).
- push, merge: 사용자의 명시적 승인 없이 절대 실행 금지 (자동화 대상 아님).
- push 전 항상 변경 파일 목록과 핵심 diff 요약을 먼저 제시할 것.

