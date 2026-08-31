# PLAN — backend-discovery

## [계획 초안] Bedrock 장애·권한 예외 대응 백엔드 회복탄력성(Graceful Fallback) 및 사서 페르소나 안내 구축

**목표:**  
AWS Bedrock 호출 시 권한 부족(`AccessDeniedException`), 레이트 리밋(`ThrottlingException`), 일시적 네트워크 장애 등이 발생해도 500 에러로 중단되지 않고, 사서 캐릭터별(블루/슈빌) 친절한 안내 메시지로 응답하여 프론트엔드의 엉뚱한 하드코딩 문구 표출을 원천 방어하고 디버깅 로그를 구조화한다.

---

### 단계별 Task 체크리스트

#### Task 1: Bedrock 예외 처리 및 사서별 Fallback 메시지 유틸리티 설계
- [x] Bedrock 관련 `botocore.exceptions.ClientError`, `BotoCoreError` 및 일반 예외를 포착하여 사서 페르소나(`librarian_id`: cat ⇄ stork)에 맞춘 친절한 사용자 안내 메시지 생성 함수 구현 (`src/discovery/domain/orchestrator/fallback.py`)
  - **블루 (고양이)**: *"냥냥... 서재 책장을 정리하던 중에 통신 연결이 잠시 끊겼다냥 🐾 잠시 후에 다시 이야기해달라냥!"*
  - **슈빌 (황새)**: *"두둥! 서재 사서실 통신에 일시적인 장애가 발생했습니다 🪶 잠시 후 다시 말씀해 주십시오."*
- [x] 에러 원인(`AccessDeniedException`, `ThrottlingException` 등)과 모델 ID, 리전을 식별할 수 있는 구조적 에러 로그(`[BEDROCK_FALLBACK]`) 출력 배선

#### Task 2: `OrchestratorService` 스트리밍 및 일반 대화 경로에 회복탄력성 배선
- [x] `stream_chat`: `agent.stream_async` 실행 및 이벤트 수신 루프에서 Bedrock 예외 발생 시, 500 전파 대신 fallback 텍스트를 청크로 yield하고 세션 히스토리에 정상 기록 후 200 스트림 종료
- [x] `chat`: `agent.invoke_async` 실행 시 예외 발생 시 fallback 텍스트를 담은 `ChatResponse` 반환

#### Task 3: 단위 테스트 작성 및 회복탄력성 검증
- [x] `tests/unit/test_orchestrator_service.py`에 `AccessDeniedException`, `ThrottlingException`, 일반 런타임 에러 시뮬레이션 테스트 4건 작성
- [x] 사서별(블루/슈빌) 안내 문구 정상 반환 및 500 방어 검증
- [x] 정적 분석(`ruff`, `mypy`) 및 단위 테스트 130건 100% 통과 확인

#### Task 4: 하네스 문서 동기화
- [x] `.harness/STATE.md`, `.harness/HANDOFF.md`, `.harness/PLAN.md` 갱신

---

### [참고] 후속 대기 과제
- 인프라팀의 Bedrock Claude Sonnet 5 IAM 권한/모델 액세스 반영 후 실호출 E2E 검증
