# PLAN — backend-discovery

## [계획 초안] Bedrock 장애·권한 예외 대응 백엔드 회복탄력성(Graceful Fallback) 및 사서 페르소나 안내 구축

**목표:**  
AWS Bedrock 호출 시 권한 부족(`AccessDeniedException`), 레이트 리밋(`ThrottlingException`), 일시적 네트워크 장애 등이 발생해도 500 에러로 중단되지 않고, 사서 캐릭터별(블루/슈빌) 친절한 안내 메시지로 응답하여 프론트엔드의 엉뚱한 하드코딩 문구 표출을 원천 방어하고 디버깅 로그를 구조화한다.

---

### 단계별 Task 체크리스트

#### Task 1: `initial_meta_timeout_seconds` 설정 추가
- [x] `src/discovery/core/config.py`의 `Settings`에 `initial_meta_timeout_seconds: float = 1.5` 필드 추가 (기본 1.5초 초고속 Fail-Fast)
- [x] `k8s/base/configmap.yaml`에 `INITIAL_META_TIMEOUT_SECONDS: "1.5"` 기본값 반영

#### Task 2: `OrchestratorService.get_initial_meta` Fail-Fast 타임아웃 및 장애 격리 배선
- [x] `src/discovery/application/orchestrator_service.py`의 `get_initial_meta`에서 사서 서버 호출(`consult`)을 `asyncio.wait_for(..., timeout=self._settings.initial_meta_timeout_seconds)`로 감싸기
- [x] 타임아웃 또는 네트워크 에러 발생 시 `[INITIAL_META_TIMEOUT]` 경고 로깅 후 지체 없이 `(None, None)` 즉시 반환하여 브라우저에 0.1초~1.5초 이내에 스트리밍 응답(`StreamingResponse`)이 열리도록 보장

#### Task 3: 단위 테스트 작성 및 회복탄력성 검증
- [x] `tests/unit/test_orchestrator_service.py`에 `get_initial_meta` 1.5초 타임아웃 발생 시 블로킹 없이 `(None, None)`을 즉시 반환하는지 검증하는 비동기 단위 테스트 3건 추가
- [x] 전체 단위 테스트 133건 및 정적 분석(`ruff`, `mypy`) 100% 통과 확인

#### Task 4: 하네스 문서 동기화 및 PR 생성
- [x] `.harness/STATE.md`, `.harness/HANDOFF.md`, `.harness/PLAN.md` 갱신
- [x] `develop` 대상 PR 생성

---

### [참고] 후속 대기 과제
- 인프라팀의 Bedrock Claude Sonnet 5 IAM 권한/모델 액세스 반영 후 실호출 E2E 검증
