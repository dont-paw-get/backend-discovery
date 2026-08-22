# PLAN — backend-discovery (CLIAR-51-Recommendation-Agent)

브랜치명을 `CLIAR-51-API-Routers`에서 `CLIAR-51-Recommendation-Agent`로 rename했다
(push된 적 없는 로컬 전용 브랜치라 로컬 rename만으로 충분, 원격 조치 불필요).
PLAN.md 제목과 브랜치명을 통일했다. PostgreSQL/RDB는 완전히 제거됐고, 남은
인프라는 Redis(`ChatSessionStore`)뿐이다.

이전에 검토했던 "별도 추천 에이전트 레포로 이관"은 취소됐다. backend-discovery
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

- [x] **Task 1: Strands Agents SDK 도입 및 기본 에이전트 팩토리** (`create_librarian_agent`, Claude 3 Haiku)
- [x] **Task 2: Tavily 도서 웹 검색 도구 구현** (`BookSearchTool`, Redis 캐시, 월간 사용량 상한)
- [x] **Task 3: ChatSessionStore 연동 및 배선** (`LibrarianService`, 멀티턴 대화 히스토리 전달/기록)
- [x] **Task 4: POST /chat 라우터 + 스트리밍 응답 + CORS 설정 + API 계약** (`docs/api/openapi.yaml`)
- [x] **Task 5: 프롬프트 캐싱 적용** (`BedrockModel` `CacheConfig(strategy="auto")` 및 `cache_tools="default"`)
- [x] **Task 6: 통합 테스트 + Docker Compose 정리** (`tests/integration/test_chat_integration.py`, `docker-compose.yml`)

## 운영 규칙 (계속 적용)

- Task 완료마다 커밋을 분리하고 `[CLIAR-51]` 태그를 붙인다.
- Task 완료 보고에는 사용자가 직접 확인 가능한 방법을 포함한다.
- push/merge는 사용자의 명시적 승인이 있을 때만 수행하며, push 전 변경 파일 목록과
  diff 요약을 먼저 제시한다.
- **Bedrock/Tavily 실제 API 호출이 필요한 테스트(비용 발생 가능)는 별도 승인 후에만
  진행한다.** 특히 Tavily는 무료 티어 크레딧 소진 위험이 있으므로, 실제 호출이
  필요한 테스트는 최소 횟수로 제한하고 사전에 알린다.

## 함께 갱신할 산출물 (AGENTS.md 동기화 정책)

- Task 4 완료 시 → `docs/api/openapi.yaml`에 `/chat` 계약 반영 (완료)
- 각 Task 완료 시 → `PLAN.md`에서 항목 제거 + `STATE.md` 단계 한 줄 갱신 (완료)
- 세션 종료 시 → `.harness/HANDOFF.md` 인수인계 append
