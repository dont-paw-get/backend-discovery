# PLAN — backend-discovery (CLIAR-51-Recommendation-Agent)

브랜치명을 `CLIAR-51-API-Routers`에서 `CLIAR-51-Recommendation-Agent`로 rename했다
(push된 적 없는 로컬 전용 브랜치라 로컬 rename만으로 충분, 원격 조치 불필요).
PLAN.md 제목과 브랜치명을 통일했다. PostgreSQL/RDB는 완전히 제거됐고, 남은
인프라는 Redis(`ChatSessionStore`)뿐이다.

이전에 검토했던 "별도 사서 에이전트 레포로 이관"은 취소됐다. backend-discovery
자체가 Strands 기반 추천 에이전트 역할을 계속 맡는다.

## 참고 문서 (구현 전 확인)

- `.harness/research/2026-08-21-strands-agents-poc-design.md` — Agent/tool 모델링
  초안(`system_prompt`로 페르소나 분리, 공용 검색은 `@tool`로 공유)
- `.harness/research/2026-08-21-librarian-agent-model-and-latency.md` — 모델 선택
  조사 당시 1차 추천은 Claude Haiku 4.5였으나, 이후 교육 계정에서 Haiku 4.5/
  Sonnet 4 이상이 전 리전 차단된 것이 확인되어 **Claude 3 Haiku**로 확정했다
  (`.harness/BACKLOG.md` 참고, `core/config.py`의 `librarian_model_id`). 속도
  최적화 기법(①스트리밍 ②프롬프트 캐싱 ③지연시간 최적화 추론 ④검색 결과 캐싱
  ⑤병렬 도구 실행)은 여전히 유효하나, ③은 Claude 3 Haiku 기준으로 지원 여부를
  재확인해야 한다(조사 시점엔 3.5 Haiku만 확인됨, 3 Haiku는 별도 확인 필요).
- `.harness/ARCHITECTURE.md` — 현재 디렉토리 구조, Redis 키 구조

## Task 목록

### Task 3: `ChatSessionStore` 연동

- 목표: 에이전트가 이전 대화 턴을 불러와 문맥을 유지하고, 답변 후 히스토리에 기록한다.
- 가이드: `ChatSessionStore.get_history(session_id)`로 이전 턴을 불러와 에이전트
  호출 시 컨텍스트로 전달. 응답 후 사용자·어시스턴트 턴을 `append_turn`으로 기록.
  Strands 자체 세션 관리 기능(있다면)과 우리 `ChatSessionStore`가 중복/충돌하지
  않는지 구현 전에 Strands 문서로 확인. `create_librarian_agent`에
  `BookSearchTool.as_tool()`을 `tools=[...]`로 연결하는 배선도 이 Task에서 한다
  (Task 2에서 도구 자체는 완성됐으나 아직 에이전트에 연결되지 않음).
- 테스트: 단위 — mocker로 `ChatSessionStore`/에이전트 대체, 히스토리 전달·기록
  순서 검증. 통합 — 같은 `session_id`로 2회 호출 시 두 번째 호출에 첫 턴이 포함되는지.
- Demo: 같은 세션으로 "추천해줘" → "더 가벼운 거 있어?"를 물으면 두 번째 응답이
  첫 질문 문맥을 반영한다.

### Task 4: `POST /chat` 라우터 + 스트리밍 응답 + API 계약

- 목표: HTTP로 에이전트를 호출할 수 있게 배선하고, 첫 토큰 지연을 최소화한다.
- 가이드: `stream_async` + FastAPI `StreamingResponse`로 스트리밍 응답 구조를
  처음부터 반영(`.harness/research/2026-08-21-librarian-agent-model-and-latency.md`
  우선순위 1번). `docs/api/openapi.yaml`에 `/chat` 계약을 다시 채운다(현재
  `paths: {}`).
- 테스트: 단위 — 라우터 mocking. E2E — 스트리밍 응답이 청크 단위로 오는지 확인.
- Demo: curl로 스트리밍 응답을 청크 단위로 받는 걸 확인, 프론트 연결 테스트.

### Task 5: 프롬프트 캐싱 + 지연시간 최적화 추론 적용 검토

- 목표: 반복되는 system_prompt/도구 정의 부분을 캐싱하고, Bedrock 지연시간
  최적화 옵션 적용 가능 여부를 확인한다.
- 가이드: Bedrock Prompt Caching을 사서 페르소나 system_prompt + 도구 스펙에
  적용. `performanceConfig.latency="optimized"`가 Claude 3 Haiku(현재 확정 모델,
  `.harness/BACKLOG.md` 참고)에서 지원되는지 구현 시점에 재확인(조사 시점엔 3.5
  Haiku만 확인됨, 3 Haiku는 별도 확인 필요).
- 테스트: 실측 응답 시간 비교(적용 전/후).
- Demo: 캐싱 적용 전/후 응답 시간을 실측해 비교 수치 제시.

### Task 6: E2E 테스트 + Docker Compose 정리

- 목표: 전체 파이프라인이 실제로 동작하는지 확인하고 로컬 개발 환경을 정리한다.
- 가이드: `docker compose up`으로 `redis` + `app`만 뜨는 상태에서 `/chat` E2E 테스트.
  `.env.example`의 `TAVILY_API_KEY`, `TAVILY_CACHE_TTL_SECONDS`,
  `TAVILY_MONTHLY_CREDIT_LIMIT`(Task 2에서 이미 추가됨)에 실제 발급받은 키를 채워
  로컬에서 실제로 동작하는지 확인한다.
- 테스트: `uv run ruff check . && uv run mypy . && uv run pytest`
- Demo: 처음부터 끝까지(질문 → 웹 검색 → 답변 → 세션 기록) 실제로 동작.

## 운영 규칙 (계속 적용)

- Task 완료마다 커밋을 분리하고 `[CLIAR-51]` 태그를 붙인다.
- Task 완료 보고에는 사용자가 직접 확인 가능한 방법을 포함한다.
- push/merge는 사용자의 명시적 승인이 있을 때만 수행하며, push 전 변경 파일 목록과
  diff 요약을 먼저 제시한다.
- **Bedrock/Tavily 실제 API 호출이 필요한 테스트(비용 발생 가능)는 별도 승인 후에만
  진행한다.** 특히 Tavily는 무료 티어 크레딧 소진 위험이 있으므로, 실제 호출이
  필요한 테스트는 최소 횟수로 제한하고 사전에 알린다.

## 함께 갱신할 산출물 (AGENTS.md 동기화 정책)

- Task 4 완료 시 → `docs/api/openapi.yaml`에 `/chat` 계약 반영
- 각 Task 완료 시 → `PLAN.md`에서 항목 제거 + `STATE.md` 단계 한 줄 갱신
- 세션 종료 시 → `.harness/HANDOFF.md` 인수인계 append
