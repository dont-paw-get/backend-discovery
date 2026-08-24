# PLAN — backend-discovery (CLIAR-86-Orchestrator-Agent)

브랜치: `CLIAR-86-Orchestrator-Agent` (`CLIAR-67-Librarian-Recommendation-Format`
기준으로 분기, `develop`에 아직 CLIAR-67이 머지되지 않은 상태에서 그 위에 얹었다.
머지 순서는 CLIAR-67 → CLIAR-86으로 맞춰야 히스토리가 깨끗하다).

## 배경 / 목표

이 레포에서 "오케스트레이터 에이전트"를 실습 목적으로 추가한다. 팀원이 별도
레포(`backend-librarian`)로 사서 페르소나 에이전트를 만들고 있으며, 이 레포의
기존 추천 에이전트(웹 검색 기반, `create_librarian_agent` + `BookSearchTool`)는
격하되지 않고 그대로 유지한다. 오케스트레이터가 최상위 진입점이 되어 사용자 의도에
따라 (1) 추천 에이전트(로컬 도구) 또는 (2) 사서 에이전트(`backend-librarian`,
HTTP 호출 도구)에게 위임하는 **Agent-as-a-Tool** 구조를 구현한다.

- 사서 에이전트(`backend-librarian`)는 완전히 별도 프로세스/레포로 독립 유지.
  이 레포는 그 서비스를 HTTP로 호출하는 도구만 갖는다(Redis 직접 공유 안 함).
- 추천 에이전트는 오케스트레이터의 로컬 도구로 장착한다(별도 LLM 호출을 한 번 더
  씌우지 않고, 지금 구조를 그대로 재사용).
- 오케스트레이터 라우팅은 Strands 기본 tool-calling(LLM 자율 도구 선택)을 사용한다
  (별도 의도 분류 로직을 추가하지 않음).
- `/api/v1/chat`은 오케스트레이터를 향하도록 바뀌지만, 요청/응답 스키마
  (`ChatRequest`/`ChatResponse`)는 그대로 유지한다(내부 구현 교체이지 계약 변경이
  아님). 계약이 실제로 바뀌지 않는지 Task 4에서 재확인한다.
- `backend-librarian`이 아직 없으므로 `consult_librarian_tool`은 URL 미설정/연결
  실패 시 고정 응답("사서 에이전트 준비 중")을 반환하는 스텁으로 먼저 구현한다.
  오케스트레이터 시스템 프롬프트에 이 스텁 응답을 사용자에게 자연스럽게 안내하라는
  지시를 포함한다(LLM이 고정 문구를 그대로 노출하지 않도록).

## Task 목록

### Task 3: 사서 에이전트 HTTP 스텁 도구

- 목표: `backend-librarian` 연동 인터페이스를 먼저 확정하고, 서비스가 없을 때도
  안전하게 동작하게 한다.
- 가이드:
  - `core/config.py`에 `librarian_agent_url: str | None = None` 추가(.env.example
    갱신 포함).
  - `consult_librarian_tool` — `@tool(name="consult_librarian")`. httpx로
    `POST {librarian_agent_url}/chat` 호출(요청/응답 형태는 이 레포의 기존
    `ChatRequest`/`ChatResponse`와 동일한 최소 계약으로 가정: `message`,
    `session_id` → `message`). URL이 `None`이거나 호출 실패(타임아웃/연결 오류/
    5xx)면 예외를 전파하지 않고 고정 문자열("사서 에이전트 준비 중입니다")을
    반환한다(`BookSearchTool.search_books`의 graceful 폴백 패턴과 동일).
  - 오케스트레이터 시스템 프롬프트에 "이 도구가 준비 중 응답을 반환하면 사용자에게
    현재 이용 불가함을 안내하고 대안(예: 추천 에이전트 이용)을 제시하라"는 지시
    포함.
- 테스트: 단위 — httpx 클라이언트를 mocker로 대체해 (1) URL 미설정 시 스텁 응답,
  (2) 연결 실패 시 스텁 응답, (3) 정상 응답 시 그대로 반환하는 3가지 경로 검증.

### Task 4: 라우터 배선 + API 계약 확인

- 목표: `/api/v1/chat`이 오케스트레이터를 호출하도록 교체한다.
- 가이드: `api/deps.py`의 `get_librarian_service` 의존성을
  `get_orchestrator_service`로 교체(또는 병행 — 기존 `LibrarianService` 의존성은
  Task 2의 로컬 도구 내부에서 여전히 쓰이므로 완전히 제거하지 않음). 라우터
  (`api/v1/routers/chat.py`)가 `OrchestratorService.chat`/`stream_chat`을 호출하도록
  변경. `ChatRequest`/`ChatResponse` 스키마가 실제로 안 바뀌는지 확인하고, 바뀌지
  않으면 `docs/api/openapi.yaml` 수정은 필요 없음(내부 구현 교체는 계약 변경이
  아니므로). 스키마가 조금이라도 바뀌면 그때 `docs/api/openapi.yaml`을 먼저
  수정한다.
- 테스트: 단위 — 라우터 mocking(기존 `test_chat_router.py` 패턴 재사용, 대상만
  `OrchestratorService`로 교체). E2E — 스트리밍 응답 정상 동작 재확인.

### Task 5: E2E 검증

- 목표: 전체 위임 흐름이 실제로 동작하는지 확인한다.
- 가이드: "비 오는 날 읽기 좋은 소설 추천해줘" → `recommend_books_tool` 호출 확인.
  "고민을 들어줘" 류 질문 → `consult_librarian_tool` 호출 시도 → 스텁 응답 확인
  (`librarian_agent_url` 미설정 상태로 검증).
- 테스트: `uv run ruff check . && uv run mypy . && uv run pytest -m "not integration"`,
  필요 시 통합 테스트 추가.
- Demo: curl로 두 종류 질문을 각각 보내 라우팅이 의도대로 동작하는지 확인.

## 운영 규칙 (계속 적용)

- Task 완료마다 커밋을 분리하고 `[CLIAR-86]` 태그를 붙인다.
- Task 완료 보고에는 사용자가 직접 확인 가능한 방법을 포함한다.
- push/merge는 사용자의 명시적 승인이 있을 때만 수행하며, push 전 변경 파일 목록과
  diff 요약을 먼저 제시한다.
- **Bedrock/Tavily 실제 API 호출이 필요한 테스트(비용 발생 가능)는 별도 승인 후에만
  진행한다.**
- `backend-librarian`이 실제로 준비되면 `librarian_agent_url` 값만 `.env`에 채워
  연동하면 되는 구조를 유지한다(코드 변경 없이 연결 가능한 것이 이 설계의 핵심 목표).

## 함께 갱신할 산출물 (AGENTS.md 동기화 정책)

- Task 4에서 API 계약이 실제로 바뀌면 → `docs/api/openapi.yaml`에 반영 + 필요 시
  `docs/api/decisions/`에 ADR 추가
- `.harness/ARCHITECTURE.md` — 오케스트레이터 도입 후 시스템 구성도·담당 기능 갱신
  (Task 1~2 완료 시점에 반영)
- 각 Task 완료 시 → `PLAN.md`에서 항목 제거 + `STATE.md`에 단계 한 줄 갱신
- 세션 종료 시 → `.harness/HANDOFF.md` 인수인계 append
