# PLAN — backend-discovery

## [제안] 단일 오케스트레이터 기반 올인원 독서 비서 (Unified Agent Assistant)

CLIAR-111 이후 착수. 8/26 세션에서 보안·구조 피드백을 반영해 Phase를 재정렬했다
(원안: 사용자 기존 계획, 재정렬 근거는 아래 각 Phase 설명 참고).

### 1. 배경 및 목표
- **문제점**: 기존엔 사용자가 [일반 검색]/[도서 추천]/[일반 대화·기록] 3가지 모드를 수동
  선택해야 했고, 복합 의도(예: "어린왕자 다 읽었는데 비슷한 책 추천해줘") 처리가 안 됨.
- **목표**: 프론트 모드 선택 UI 제거, 단일 자연어 입력창 + 오케스트레이터가 의도를 판단해
  도구를 라우팅하는 Zero-Friction 올인원 독서 비서.

### 2. 4대 도구 구성 (목표 아키텍처)
```
1. 내 서재 검색(search_my_library) — 실제로는 discovery가 만드는 게 아니라
   Basic API(backend-book류)의 기존 CRUD 엔드포인트를 호출하는 프록시 도구
2. 도서 추천(recommend_books) — 기존, Tavily 웹 검색
3. 사서 대화/상담(consult_librarian) — 기존, backend-librarian HTTP
4. 독서 활동 관리(manage_reading_activity) — 진척도 갱신/스크랩 생성 등 쓰기
```

### 3. 단계별 로드맵

#### Phase 0: 조율 구조 확정 + 회귀 기준선 고정 (신규 — 코드 최소, 계약/문서 위주)
- [ ] 오케스트레이터가 "위임자"가 아니라 "멀티툴 에이전트 하나"처럼 보이는 문제(8/25 지적)
      재확인 — `ORCHESTRATOR_SYSTEM_PROMPT`가 실행 세부까지 지시하는지 점검
- [ ] `extract_fallback_text`의 무차별 toolResult 결합 로직을 화이트리스트 방식으로 명시화
      (도구가 늘어나면 `search_my_library`/`manage_reading_activity`의 원시 반환값이
      그대로 사용자 화면에 노출될 위험 — Phase 3 착수 전 반드시 선행)
- [ ] 기존 마크다운 계약(CLIAR-67/91/114)에 대한 회귀 테스트 존재 확인/보강

#### Phase 1: 원서 vs 정발본 인터랙티브 대화 (기존 Phase 2)
- [ ] 규칙 7(해외 도서 한국어 번역) 재작성 — 제목 헤더(`### 📖`)는 한국어 표준명 유지,
      원제는 별도 라인(`- **원제**:`)으로 분리해 CLIAR-114 번역 지침과 충돌 없이 원제 보존
- [ ] 정발본 안내 멘트 유도, 멀티턴 정발본 재검색 체이닝(`search_books("{도서명} 한국어판")`)
- [ ] `tests/unit/test_librarian_agent.py` 등 기존 assert 갱신

#### Phase 2: 내 서재 검색 (읽기 전용)
- [ ] **선결 (팀원 의존, discovery 단독 결정 불가)**: 인증 방식 확정 — discovery가 사용자
      인증 토큰을 Basic API로 패스스루하는 방식(A안, 권장) vs discovery가 자체 JWT 검증 후
      `user_id`를 추출해 넘기는 방식(B안). **`user_id`를 도구(tool) 함수 파라미터로 LLM이
      채우게 하는 설계(C안)는 IDOR 위험으로 채택하지 않음** — 신원 정보는 요청 인증에서
      서버가 직접 추출해 도구 생성 시 클로저로 주입해야 한다(`RecommendBooksTool`/
      `ConsultLibrarianTool`과 동일 패턴).
- [ ] `SearchMyLibraryTool`(HTTP 프록시 도구, `ConsultLibrarianTool`과 동일 패턴) 구현 —
      도구 함수 인자는 `query`만, 인증 컨텍스트는 서비스 레이어가 주입
- [ ] Basic API 계약 확정 필요(엔드포인트, 응답 스키마) — 팀원 의존 항목

#### Phase 3: 독서 활동 관리 (쓰기 — Phase 2와 분리)
- [ ] `manage_reading_activity` 쓰기 안전장치 설계: `action_type` 화이트리스트 검증,
      멱등키 또는 확인 2턴 패턴, 잘못된 `book_id` 처리
- [ ] `TRIGGER_NAVIGATE`(화면 이동)는 쓰기 도구에서 제외 — Phase 4 Action Payload로 이동
      (화면 이동은 상태 변경이 아니므로 관심사 분리)
- [ ] Phase 2와 동일한 인증 주입 패턴 적용

#### Phase 4: 프론트엔드 연동 및 Action Payload 규격화
- [ ] 스트리밍 wire 계약 변경(현재 `text/plain` 순수 스트림 → Action 메타데이터 포함)은
      `docs/api/decisions/`에 ADR로 먼저 확정 후 진행. 선택지: SSE 정식 전환 vs 텍스트 스트림
      유지 + 종단 구분자 뒤 JSON 한 줄. 프론트 담당자와 사전 합의 필요
- [ ] 프론트 모드 선택 UI 제거, 단일 스트리밍 챗 인터페이스 배선
- [ ] `docs/api/openapi.yaml` 동기화

### [대기/엔지니어링 과제] 성능 최적화
- [ ] 직결 스트리밍 파이프라인(하위 에이전트 토큰 즉시 반환, Early Stop)
- [ ] Pydantic Structured Output 규격화
- [ ] Phase별 "체감 첫 토큰 시간 회귀 없음" 측정 기준 도입 검토 (도구 4개로 늘어나며
      라우팅 왕복 증가 → 레이턴시 저하 우려, 백로그의 "2~3초대 단축" 목표와 상충 방지)
