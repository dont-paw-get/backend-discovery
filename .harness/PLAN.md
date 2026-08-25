# PLAN — backend-discovery

현재 진행 중인 활성 계획 없음 (CLIAR-103 도서 장르 분류 API 신설 및 backend-book genre_type 동기화 완료).

## [대기/후속 제안] 에이전트 엔지니어링 및 성능 최적화

사용자 컨펌 후 새 티켓 브랜치에서 진행할 항목:

- [ ] **1단계: `recommend_books` 도구 시그니처에 `count: int = 1` 파라미터 구조화 적용**
  - 프롬프트에만 의존하던 권수 제어를 함수 시그니처 레벨로 명시.
- [ ] **2단계: 직결 스트리밍 파이프라인(Direct Streaming Pipeline) 구축**
  - 상위 오케스트레이터의 2차 생성 대기 시간을 단축하기 위해 하위 추천 에이전트의 토큰을 즉시 반환하는 직결 스트리밍 파이프라인 구성.
- [ ] **3단계: Pydantic Structured Output을 통한 JSON 응답 고도화**
  - 비정형 마크다운 파싱 대신 Bedrock/Strands의 Structured Output을 활용한 응답 규격화.
