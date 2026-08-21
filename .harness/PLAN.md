# PLAN — backend-discovery (CLIAR-51-API-Routers)

## CLIAR-51. API 라우터 구현

(Step 3, Task 9~13 진행 중)

---

## Task 상세

### CLIAR-51 — API 라우터 구현
(원래 계획의 Step 3에 해당. CLIAR-40 핵심 코드 구현 완료 후 별도 티켓으로 분리 확정.)

**Task 10: `POST /internal/sync-book`**
- 목표: Basic API가 보낸 도서 데이터를 임베딩해 읽기 모델에 멱등 반영한다. 단건·실시간·테스트용이며 대량 적재 수단이 아니다(CSV 배치는 별도 티켓, `.harness/BACKLOG.md` 참고).
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
- Task 9 완료 시 → `docs/api/openapi.yaml` 확정 + `docs/api/decisions/0001-internal-sync-contract.md` ADR 작성
- 각 Task 완료 시 → `PLAN.md`에서 항목 제거 + `STATE.md` 단계 한 줄 갱신
- 세션 종료 시 → `.harness/HANDOFF.md` 인수인계 append

## 운영 규칙 (CLIAR-51)
- Task 완료마다 커밋을 분리하고 `[CLIAR-51]` 태그를 붙인다.
- Task 완료 보고에는 사용자가 직접 확인 가능한 방법(curl, psql, `/docs` Swagger UI 등)을 포함한다.
- push/merge는 사용자의 명시적 승인이 있을 때만 수행하며, push 전 변경 파일 목록과 diff 요약을 먼저 제시한다.
- Bedrock 실제 API 호출이 필요한 테스트(비용 발생 가능)는 별도 승인 후에만 진행한다.
