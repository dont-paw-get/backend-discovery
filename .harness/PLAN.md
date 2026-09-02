# PLAN — backend-discovery

## 진행 순서 (2026-09-01 확정)

CLIAR-171과 CLIAR-216이 `src/discovery/domain/orchestrator/agent.py`의 같은 페르소나 프롬프트 상수를 건드리므로 병행하지 않는다.
프롬프트를 **축소하는 작업(CLIAR-171)이 확장하는 작업(CLIAR-216)보다 먼저**다.

| 순서 | 티켓 | 범위 | 선행 조건 |
| --- | --- | --- | --- |
| 1 | **CLIAR-158** | ✅ **완료·develop 머지** (Task 1·2 코드 구현 완료 및 머지. Task 3~5는 dev 실측 필요 — 별도 스파이크로 처리) | 없음 |
| 2 | **CLIAR-215** (QA기반 최적화a) | ✅ **완료** — Task 1(실측 러너 및 실측 완료)·Task 2(인증 Presence Check, 401, ADR 0007)·Task 3(위기 109 핫라인 게이트)·Task 4(공백 422 및 입력 게이트)·Task 5(P1 회귀 확인)·Task 6(단위 테스트 196건 통과) | 없음 |
| 3 | **CLIAR-171** | ✅ **완료** — Task 1-0(search_books 페이로드 축소) + Task 1(오케스트레이터 카드 재생성 제거 및 splice 결합) + Task 2(리전/프로필 비교) + Task 3(추론 파라미터 튜닝) | CLIAR-215 완료 |
| 4 | **CLIAR-216** (QA기반 최적화b) | 🔄 **진행 중 (다음 착수 대상)** — 공통 가드레일 리팩터 + 안전·엣지·환각·감정 프롬프트 고도화 | CLIAR-171 완료 |

순서 근거: (1) CLIAR-158은 충돌 대상이 없는 순손실 제거이고 계측 기반이 이후 티켓의 판단 근거가 된다. (2) CLIAR-171이 프롬프트를 줄인 뒤에 CLIAR-216이 확장해야 재작업과 회귀 원인 혼선을 피할 수 있다. (3) CLIAR-215는 P1 안전성·인증 공백을 다루지만 구현 위치가 입력 게이트 코드와 `api/deps.py`라 프롬프트와 충돌하지 않아 앞으로 당겼다. 계획 확정 시 이 근거를 `.harness/DECISIONS.md`에 기록했다.

---

### [진행 중] CLIAR-158: 순손실 제거 및 레이턴시 계측 (Task 1·2 완료·develop 머지, Task 3~5는 후속 실측 과제)

브랜치: (머지 완료, `CLIAR-158-Latency-Observability`는 삭제됨)

Task 1(계측 모듈 & 개인정보 화이트리스트 필터링), Task 2-1(tail consult 버그 수정 & 1.5s/20s 타임아웃), Task 2-2(prefetch 결과 1회차 재사용 & 라우터 signals fallback)는 구현 완료되어 `origin/develop`에 머지됨.

#### 남은 실측 과제 (dev 배포 필요)

- [ ] **Task 3: 프롬프트 캐싱 dev 환경 히트 및 비용 실측**
  - [ ] `Settings.enable_prompt_caching` 런타임 배선 완료됨 (현재 기본값 `False` 안전 유지).
  - [ ] dev 배포 후 캐시 TTL 5분 내 연속 3턴 실행하여 `accumulated_usage.cacheReadInputTokens > 0` 실측.
  - [ ] 트래픽 패턴상 캐시 쓰기 비용 대비 읽기 이득이 확인되면 기본 활성화(`True`), 손해이면 `False` 확정 및 근거 기록.
- [ ] **Task 4: reasoning/thinking 기본 동작 확인**
  - [ ] Bedrock 측 기본 동작으로 reasoning 토큰이 발생하는지 Task 1 로그(`outputTokens` 대비 실제 응답 길이)로 실측 확인.
- [ ] **Task 5: 전후 비교표 작성 및 문서 동기화**
  - [ ] 시나리오 4종 × 3회 전후 비교표 작성 (TTFB, 총 소요, `consult` 호출 횟수, 입출력·캐시 토큰).
  - [ ] `STATE.md` 단계 완료 갱신, `HANDOFF.md` 인수인계.

---

### [상세 계획 수립 대상] CLIAR-216: QA 데이터셋 기반 가드레일 및 프롬프트 고도화 (다음 착수 대상)

브랜치: `CLIAR-216-Prompt-Guardrails` (CLIAR-171 머지 후 `develop`에서 분기)

- [ ] **Task 1: 블루/슈빌 프롬프트 공통 가드레일(`SHARED_GUARDRAILS`) 모듈화 리팩터링**
  - `agent.py`에서 중복되는 도구 분기/서재 안내/안전 가드레일을 공통 상수로 분리하고 페르소나 어조만 조합하도록 정돈
- [ ] **Task 2: QA 46건 실측 기반 프롬프트 엣지 케이스 보강**
  - 환각 방지(없는 책 지어내기 방어 지침 강화), 감정/위로 대화의 페르소나 공감 톤 보강
- [ ] **Task 3: QA 러너(`scripts/qa_runner.py`) 전체 46건 재실측 및 통과율 검증**
- [ ] **Task 4: 정적 분석, 단위 테스트 갱신 및 문서 동기화**

### 백로그로 이관 (이번 범위 제외)

- **직결 스트리밍(Bypass) 아키텍처 변경**: Agent-as-a-Tool의 `str` 반환 계약상 불가. 의도 분기를 서비스 레이어 코드로 이관해야 하며 CLIAR-208/213의 프롬프트 분기 재구현 + `switch_to`/`signals`/`library_books` 배선 전면 영향. CLIAR-171 Task 1의 효과 측정 후 필요성 재판단
- **Early Stop(권수 충족 시 조기 중단)**: 중단할 스트림이 없고 `truncate_books_by_count`와 충돌. 기본 2권 + 수량 엄수 프롬프트로 기대 이득 이미 회수됨
- **`signals`를 헤더에서 SSE 첫 이벤트로 이관**: `get_initial_meta`의 TTFB 하한을 구조적으로 없애는 방법이지만 ADR 0003/0005 계약 변경 + 프론트 동반 수정 필요. CLIAR-158 Task 2로 실질 해소되는지 먼저 확인
- **Bedrock Guardrails 검토**: 지연을 **증가**시키므로 레이턴시 최적화 티켓과 상충. 내용상 CLIAR-215 Task 3과 중복이므로 그쪽에서 "코드 게이트 vs Guardrails" 비교로 다룬다
