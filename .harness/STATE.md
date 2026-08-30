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
| CLIAR-91 추천 에이전트 엔지니어링 고도화 | ✅ 완료 | Task 1(RecommendBooksTool count 파라미터 구조화, clamp 1~5, 순수 함수 truncate_books_by_count 결정론적 후처리 상한 강제)·Task 2(출판사/실제 쪽수 수집 가이드 및 - **저자**: {저자} ({페이지수}쪽) 마크다운 표준화)·Task 3(과잉 사과 방지 및 당당한 사서 톤앤매너 프롬프트)·Task 4(스트리밍 파이프라인 점검 및 직결 스트리밍 전환 설계) 모두 완료. 정적 분석 100% 통과, 단위 테스트 106건 + Redis 통합 테스트 15건 전체 통과 |
| CLIAR-114 추천 에이전트 해외 도서 한국어 번역 지침 및 프롬프트 정돈 | ✅ 완료 | Task 1(LIBRARIAN_SYSTEM_PROMPT 톤앤매너 압축, 번역가 대신 원작자 표기 명시, 7번 해외 도서 번역 지침 추가)·Task 2(단위 테스트 갱신 및 106건 전체 통과)·Task 3(C안 후처리 fallback 백로그 기록 및 하네스 문서 동기화) 완료 |
| CLIAR-111 사서 에이전트(backend-librarian) 실연동 및 세션/시그널 조율 | ✅ 완료 | Task 1(설정 분리)·Task 2(API 계약 확장: 좌표 및 switch_to)·Task 3(사서 응답 DTO 및 ConsultLibrarianTool 재작성)·Task 4(ChatSessionStore 세션별 활성 사서/좌표 메타 관리)·Task 5(switch_to 세션 갱신 및 응답 반영)·Task 6(signals 포맷팅 및 추천 반영 지침)·Task 7(discovery 8001 포트 분리)·Task 8(단위 테스트 110건 100% 통과)·Task 9(ADR 0003 작성 및 문서 동기화) 모두 완료 |
| CLIAR-111 자체 완결형 사서 페르소나/지능형 스위칭 및 검색/시그널 튜닝 | ✅ 완료 | 원격 사서 서버 장애 대비 Discovery 자체 지능형 페르소나/switch_to 판단 엔진 내장(고양이 ➔ SF/경영 시 황새 사서 전환, 황새 ➔ 시/에세이 시 고양이 사서 전환), ChatResponse 및 스트리밍(X-Signals 헤더)에 날씨/시간대/무드 signals 전달 완성, 도서 검색 쿼리 1회 압축 및 기본 추천 2권 고정으로 레이턴시 2초대 단축, 프론트 단계별 점진적 진행 UX 및 왼쪽 정렬 완료. 단위 테스트 110건 100% 통과 |
| 사서별(블루 ⇄ 슈빌) 동적 페르소나 주입 및 프론트엔드 말풍선/UI 일체화 | ✅ 완료 | backend-librarian의 공식 페르소나 정의(블루: ~다냥 🐾 + 미스터리 특화 ⇄ 슈빌: 두둥! + 공손체 🪶 + 비즈니스 특화)를 오케스트레이터 및 도서 추천 에이전트에 1:1 완벽 이식하여 톤 뒤죽박죽 원천 차단, 프론트 말풍선(LibrarianCursor) 및 로딩/전환 멘트 사서별 100% 동기화 완료. 단위 테스트 112건 통과 |
| 슈빌 '두둥!' 로딩 멘트 반영 & 프리미엄 도서 카드(Book Card) 박스 UI 개선 | ✅ 완료 | 프론트엔드 로딩 멘트에 슈빌의 시그니처 '두둥!' 반영, MarkdownRenderer에서 `### 📖` 도서 블록을 감각적인 북 카드(제목 뱃지 + 저자/쪽수 칩 + 추천이유 박스) 컴포넌트로 묶어 렌더링하도록 UI 대폭 미려화 완료 |
| CLIAR-152 올인원 독서 비서 (내 서재 CRUD API 연동 및 복합 의도 오케스트레이션) | ✅ 완료 | Task 1(LIBRARY_API_URL 설정 및 DTO 모델링)·Task 2(SearchMyLibraryTool HTTP 도구 및 필터링)·Task 3(Authorization 토큰 패스스루 배선)·Task 4(블루/슈빌 서재 및 복합 추천 분기 프롬프트 주입)·Task 5(fallback 결합 안전장치 보강 및 단위 테스트 121건 통과)·Task 6(ADR 0004 작성 및 하네스 문서 동기화) 모두 완료 |
| 도서 장르 분류 API의 ISBN 필드 지원 및 LLM 식별 강화 | ✅ 완료 | Task 1(openapi.yaml 및 BookClassificationRequest에 isbn optional 필드 추가)·Task 2(도메인 프롬프트 및 서비스 배선)·Task 3(단위 테스트 123건 및 정적 분석 100% 통과)·Task 4(ADR 0002 및 하네스 문서 동기화) 모두 완료 |
| 에이전트 서비스 활용 유도(CTA) 및 과잉 도구/장문 줄거리 방어 가드레일 보강 | ✅ 완료 | Task 1(블루/슈빌 오케스트레이터 프롬프트에 서재 조회 시 외부 도구 차단, 장문 줄거리 금지 및 1~2줄 CTA 추가)·Task 2(추천 에이전트 추천 이유 2~3문장 콤팩트 상한 및 줄거리/스포일러 금지)·Task 3(단위 테스트 123건 및 정적 분석 100% 통과) 모두 완료 |


