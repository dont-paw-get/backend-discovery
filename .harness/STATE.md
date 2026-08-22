# STATE — backend-discovery

단계 단위 완료 스냅샷. 세션별 서술은 `HANDOFF.md`에 남긴다.

| 단계 | 상태 | 요약 |
| --- | --- | --- |
| 하네스 문서 세팅 | ✅ 완료 | `.harness/` 6종 문서 + `docs/api/` 뼈대 생성, AGENTS.md origin 주소 정정 |
| 계획 수립 | ✅ 계획 수립 완료 | 3스텝(인프라 → 핵심 코드 → API 라우터) 체크리스트를 `PLAN.md`에 확정 |
| CLIAR-21 인프라 세팅 | ✅ 완료 | Task 1(pyproject.toml+uv.lock, boto3), Task 2(docker-compose·Dockerfile·.env.example), Task 3(FastAPI 앱·/health, db+redis+app 컨테이너 healthy), Task 4(Alembic async 초기화 + pgvector 확장 리비전, `db_session`/`client` 픽스처, 통합 테스트 2건 통과) 모두 완료. develop에 머지됨 |
| CLIAR-40 핵심 코드 구현 | ⚠️ 완료 후 폐기 | Task 5(`books` 모델), Task 6(DTO+BookRepository), Task 7(Bedrock Mocking+실 클라이언트, `LLM_PROVIDER` 스위치)은 구현·검증까지 완료됐으나 2026-08-21 방향 전환으로 폐기되어 `archive/vector-search-poc/`로 이동함(`.harness/DECISIONS.md` 참고). **Task 8(Redis `ChatSessionStore` — append/get 순서, LTRIM 상한, sliding window TTL, clear, 통합 테스트 4건)만 유효하게 완료 상태로 남음.** `CHAT_HISTORY_MAX_TURNS`/`CHAT_SESSION_TTL_SECONDS`는 환경변수로 조절 가능 |
| CLIAR-51 API 라우터 구현 | ⚠️ 부분 완료 후 폐기·취소 | Task 9(계약 확정)·Task 10(`/internal/sync-book`)은 구현까지 완료됐으나 2026-08-21 방향 전환으로 폐기되어 `archive/vector-search-poc/`로 이동함. Task 11(큐레이션)·Task 12(chat)·Task 13(배선)은 착수 전 취소됨 (`.harness/DECISIONS.md`, `.harness/PLAN.md` 참고) |
| 방향 전환: 벡터DB 폐기, PostgreSQL 완전 제거, 추천 에이전트로 재설계 | ✅ 완료 | 벡터DB(pgvector) 기반 자체 벡터 인덱스·검색 폐기, `archive/vector-search-poc/`로 코드 이동. PostgreSQL/SQLAlchemy(async)/asyncpg/Alembic/testcontainers(postgres) 완전 제거(RDB로 남는 데이터 없음) — `db/`, `alembic/` 삭제, `docker-compose.yml`의 `db` 서비스 제거, `Settings.database_url` 제거. backend-discovery는 별도 레포로 이관하지 않고 존속하며, 자체가 Strands 기반 "추천 에이전트" 역할을 맡는다(이전 "별도 사서 에이전트 레포 이관" 결정을 뒤집음). `ChatSessionStore`(Redis)만 유지. 웹 검색 도구는 Tavily로 확정. S3 Vectors 조사·Strands Agents SDK 조사·모델/속도 조사 결과가 이 결정의 배경(`.harness/research/` 참고) |
| CLIAR-51 추천 에이전트 (Strands 기반) | 🚧 진행 중 | Task 1(`strands-agents` 의존성, `create_librarian_agent` 팩토리, Claude 3 Haiku 확정) 완료. Task 2(`BookSearchTool` — Tavily `AsyncTavilyClient`, `search_depth="basic"` 고정, `SearchResultCache`(Redis, TTL 1일)로 캐싱, `SearchUsageLimiter`(월간 900회 상한, 캐시 히트는 카운트 제외)로 사용량 방어, Tavily 예외 전부 graceful 폴백(빈 결과), 단위 테스트 8건 통과, 통합 테스트 9건 작성(Docker 필요, 이번 세션엔 미실행)) 완료. Task 3(`ChatSessionStore` 연동 + 도구 배선)부터 진행 예정 |
