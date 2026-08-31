# ADR 0003: 사서 에이전트(backend-librarian) 실연동 및 세션/시그널 조율 아키텍처

- **상태**: 승인됨 (Accepted)
- **날짜**: 2026-08-27
- **관련 티켓**: CLIAR-111

## 컨텍스트 (Context)
DPYB 서비스는 사용자에게 페르소나 기반 사서 상담 및 상황별 도서 추천을 제공한다.
외부 독립 마이크로서비스인 `backend-librarian`과의 연동을 위해 다음 요구사항을 충족해야 했다:
1. 최상위 오케스트레이터(Strands)가 사용자 질의에 따라 사서 에이전트(`POST /api/v1/chat`)를 원격 도구(`ConsultLibrarianTool`)로 호출한다.
2. 사서 에이전트가 반환하는 `signals`(날씨, 사용자 감정/무드, 장르 포커스)를 도서 추천(`recommend_books`)에 자연스럽게 전달해야 한다.
3. 사서 에이전트가 다른 페르소나로의 전환을 제안(`switch_to`)할 경우, 세션의 활성 사서 ID를 갱신하고 클라이언트에 구조화된 필드로 전달해야 한다.
4. 사용자 위치 좌표(`latitude`/`longitude`)는 세션 최초 1회만 받아 캐시하고, 사서 상담 시 날씨 큐레이션용으로 전달해야 한다.
5. LLM 도구 호출 인자는 `message`만 노출하고 세션 ID, 사서 ID, 좌표는 서버 클로저로 주입하여 IDOR 취약점을 원천 차단해야 한다.

## 결정 사항 (Decisions)
1. **API 계약 확장 (`openapi.yaml`)**:
   - `ChatRequest`에 선택적 `latitude`, `longitude` 좌표 필드를 추가.
   - `ChatResponse`에 `switch_to` (`id`, `name`, `icon`, `genres`) 선택적 필드를 추가.
2. **세션 메타데이터 관리 (`ChatSessionStore`)**:
   - Redis `chat:session:{session_id}:meta` 키를 신설하여 활성 `librarian_id`와 사용자 좌표를 sliding TTL로 관리.
3. **DTO 및 신호 포맷팅 (`LibrarianResponse` & `ConsultLibrarianTool`)**:
   - 사서 응답을 `LibrarianResponse` DTO(Pydantic)로 엄격히 파싱.
   - `signals` 정보를 오케스트레이터 LLM에게 `[사서 분석 정보]` 텍스트 블록으로 포맷팅하여 반환, 오케스트레이터가 `recommend_books` 호출 시 쿼리에 반영하도록 프롬프트 지침 연계.
4. **포트 분리**:
   - `docker-compose.yml`에서 discovery 서비스 호스트 포트를 `8001`로 이동하여 사서 서비스(`8000`)와의 로컬 충돌을 방지.

## 결과 및 영향 (Consequences)
- 사서 에이전트와의 HTTP 통신 장애 시 graceful fallback 스텁을 반환하여 전체 대화 파이프라인의 내구성을 확보함.
- 세션별 활성 사서 및 위치 정보가 안전하게 유지되어 날씨 기반 큐레이션 및 페르소나 전환 인터랙션이 완성됨.
