# STATE — backend-discovery

단계 단위 완료 스냅샷. 세션별 서술은 `HANDOFF.md`에 남긴다.

| 단계 | 상태 | 요약 |
| --- | --- | --- |
| 하네스 문서 세팅 | ✅ 완료 | `.harness/` 6종 문서 + `docs/api/` 뼈대 생성, AGENTS.md origin 주소 정정 |
| 계획 수립 | ✅ 계획 수립 완료 | 3스텝(인프라 → 핵심 코드 → API 라우터) 체크리스트를 `PLAN.md`에 확정 |
| CLIAR-21 인프라 세팅 | ✅ 완료 | Task 1(pyproject.toml+uv.lock, boto3), Task 2(docker-compose·Dockerfile·.env.example), Task 3(FastAPI 앱·/health, db+redis+app 컨테이너 healthy), Task 4(Alembic async 초기화 + pgvector 확장 리비전, `db_session`/`client` 픽스처, 통합 테스트 2건 통과) 모두 완료. develop에 머지됨 |
| CLIAR-40 핵심 코드 구현 | ✅ 완료 | Task 5(`books` 모델), Task 6(DTO+BookRepository), Task 7(Bedrock Mocking+실 클라이언트, `LLM_PROVIDER` 스위치), Task 8(Redis `ChatSessionStore` — append/get 순서, LTRIM 상한, sliding window TTL, clear, 통합 테스트 4건) 모두 완료. `CHAT_HISTORY_MAX_TURNS`/`CHAT_SESSION_TTL_SECONDS`는 환경변수로 조절 가능 |
