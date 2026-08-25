# STATE — backend-discovery

단계 단위 완료 스냅샷. 세션별 서술은 `HANDOFF.md`에 남긴다.

| 단계 | 상태 | 요약 |
| --- | --- | --- |
| 하네스 문서 세팅 | ✅ 완료 | `.harness/` 6종 문서 + `docs/api/` 뼈대 생성, AGENTS.md origin 주소 정정 |
| 계획 수립 | ✅ 계획 수립 완료 | 3스텝(인프라 → 핵심 코드 → API 라우터) 체크리스트를 `PLAN.md`에 확정 |
| CLIAR-21 인프라 세팅 | ✅ 완료 | Task 1(pyproject.toml+uv.lock, boto3), Task 2(docker-compose·Dockerfile·.env.example), Task 3(FastAPI 앱·/health, db+redis+app 컨테이너 healthy), Task 4(Alembic async 초기화 + pgvector 확장 리비전, `db_session`/`client` 픽스처, 통합 테스트 2건 통과) 모두 완료. develop에 머지됨 |
| CLIAR-40 핵심 코드 구현 | ⚠️ 완료 후 폐기 | Task 5(`books` 모델), Task 6(DTO+BookRepository), Task 7(Bedrock Mocking+실 클라이언트, `LLM_PROVIDER` 스위치)은 구현·검증까지 완료됐으나 2026-08-21 방향 전환으로 폐기되어 `archive/vector-search-poc/`로 이동함(`.harness/DECISIONS.md` 참고). **Task 8(Redis `ChatSessionStore` — append/get 순서, LTRIM 상한, sliding window TTL, clear, 통합 테스트 4건)만 유효하게 완료 상태로 남음.** `CHAT_HISTORY_MAX_TURNS`/`CHAT_SESSION_TTL_SECONDS`는 환경변수로 조절 가능 |
| CLIAR-51 API 라우터 구현 | ⚠️ 부분 완료 후 폐기·취소 | Task 9(계약 확정)·Task 10(`/internal/sync-book`)은 구현까지 완료됐으나 2026-08-21 방향 전환으로 폐기되어 `archive/vector-search-poc/`로 이동함. Task 11(큐레이션)·Task 12(chat)·Task 13(배선)은 착수 전 취소됨 (`.harness/DECISIONS.md`, `.harness/PLAN.md` 참고) |
| 방향 전환: 벡터DB 폐기, PostgreSQL 완전 제거, 추천 에이전트로 재설계 | ✅ 완료 | 벡터DB(pgvector) 기반 자체 벡터 인덱스·검색 폐기, `archive/vector-search-poc/`로 코드 이동. PostgreSQL/SQLAlchemy(async)/asyncpg/Alembic/testcontainers(postgres) 완전 제거(RDB로 남는 데이터 없음) — `db/`, `alembic/` 삭제, `docker-compose.yml`의 `db` 서비스 제거, `Settings.database_url` 제거. backend-discovery는 별도 레포로 이관하지 않고 존속하며, 자체가 Strands 기반 "추천 에이전트" 역할을 맡는다(이전 "별도 에이전트 레포 이관" 결정을 뒤집음). `ChatSessionStore`(Redis)만 유지. 웹 검색 도구는 Tavily로 확정. S3 Vectors 조사·Strands Agents SDK 조사·모델/속도 조사 결과가 이 결정의 배경(`.harness/research/` 참고) |
| CLIAR-51 추천 에이전트 (Strands 기반) | ✅ 완료 | Task 1(strands-agents 팩토리)·Task 2(BookSearchTool Tavily 검색 도구)·Task 3(LibrarianService 세션 연동 및 도구 배선)·Task 4(POST /chat 및 /api/v1/chat 라우터, 스트리밍 응답, CORS 설정, openapi.yaml 계약)·Task 5(Bedrock 프롬프트 자동 캐싱 CacheConfig 적용)·Task 6(Redis Testcontainers 멀티턴 대화 통합 테스트 및 docker-compose 정리) 모두 완료. 단위 테스트 22건 통과, 통합 테스트 5건 작성 완료 |
| CLIAR-67 프론트엔드 도서 등록 연동 및 검색 최적화 | ✅ 완료 | Task 1(사서 시스템 프롬프트에 `### 📖 {도서 제목}`, `- **저자**:`, `- **추천 이유**:` 마크다운 템플릿 명시 및 단위 테스트 추가), Task 2(BookSearchTool 도구 설명 및 검색 가이드 최적화), Task 3(정적 분석 및 단위 테스트 25건 전체 통과) 완료 |
| CLIAR-86 오케스트레이터 에이전트 구축 | ✅ 완료 | Task 1(OrchestratorService 뼈대), Task 2(RecommendBooksTool 로컬 도구), Task 3(ConsultLibrarianTool HTTP 스텁 도구 및 fallback), Task 4(/api/v1/chat 라우터 배선 및 openapi.yaml 계약 동기화), Task 5(E2E 라우팅 및 통합 테스트, 도구 결과 마크다운 자동 결합 안전장치 추가, 단위 47건·통합 1건 통과) 모두 완료 |
| CLIAR-103 도서 장르 분류 API 신설 및 backend-book enum 규격 일치 | ✅ 완료 | `POST /api/v1/classify-genre` 신설. `backend-book`의 16개 표준 `genre_type` Enum(`SCIENCE_FICTION`, `LITERARY_FICTION`, `POETRY_DRAMA`, `BUSINESS_ECONOMICS`, `ARTS`, `COMPUTER_IT`, `NONE` 등)과 100% 동기화, 제로샷 프롬프트 및 `NONE` fallback 처리, 단위 테스트 98건 통과 |
