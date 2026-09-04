# PLAN — backend-discovery

## [보류 · 통합 범위 미확정] 사서 에이전트(backend-librarian) → backend-discovery 통합

사용자가 이번 세션에서 보류를 명확히 함. 재개 시 먼저 확정할 것:
1. 범위: (a) 원격 HTTP 연동 제거 + 기존 로컬 페르소나 엔진(`evaluate_local_persona_response`)
   단독 사용으로 전환, 아니면 (b) `backend-librarian` 레포의 실제 에이전트/프롬프트 코드를
   이 레포로 물리적 이전(별도 프로세스 제거).
2. (b)라면 `backend-librarian`이 다른 팀원 소유 레포인지, 이관 시 그 레포를 폐기해도 되는지
   먼저 확인 필요.

---

## [코드 완료 · IAM 승인 완료 · dev 배포/실측 대기] CLIAR-276: Bedrock 비용·캐시 관측 (CloudWatch)

브랜치: `CLIAR-276-Bedrock-Cost-Cache-Observability` (`develop`에서 분기, 2026-09-04)

**배경**: 기존 관측 스택(Prometheus/Grafana/Loki/Tempo)은 인프라 레벨을 커버하지만
LLM 파이프라인 자체의 비용(USD)·캐시 히트율은 비어 있었다. 사용자가 "기존 모니터링을
절대 건드리지 말 것"을 명시해, `core/metrics.py`(공유 Prometheus)에 얹는 대신 **AWS
CloudWatch 커스텀 메트릭 기반의 완전 분리 경로**로 구현했다(세부 근거는
`.harness/DECISIONS.md` 2026-09-04 참고). 범위는 Sonnet 5 단일 모델(현재 서비스가
실제로 쓰는 유일한 모델).

**구현 완료 (Task 1~6, 코드 세부는 `.harness/STATE.md`)**:
- Task 1: `core/pricing.py` — Sonnet 5 단가 dict + `estimate_cost_usd` 순수 함수.
- Task 2: `core/cloudwatch_metrics.py`(신규, 격리) — `CloudWatchMetricsPublisher`,
  네임스페이스 `DPYB/Discovery/LLM`, 기본 OFF, 실패 시 조용히 무시.
- Task 3: `orchestrator_service.py`에 `_publish_cloudwatch_usage_metrics` 배선(기존
  `log_agent_metrics` 유지, fire-and-forget), `deps.py`에 DI 추가.
- Task 4: `book_search_tool.py`의 캐시 히트/미스 분기에 발행 훅 추가(프롬프트 캐시는
  Task 3의 `cacheReadInputTokens`로 이미 처리됨).
- Task 5: `core/config.py`에 `enable_cloudwatch_metrics`(기본 False) 플래그, `.env.example` 반영.
- Task 6: `ruff`/`mypy`(84파일) 통과, `pytest -m "not integration"` 281건 전체 통과(무회귀,
  +19건 신규). 기존 4개 파일 diff가 전부 순수 추가(+111줄/-0줄)임을 `git diff --stat`으로
  확인 — 기존 로직 무변경. `core/metrics.py`/`tracing.py`/`observability.py`/ServiceMonitor
  등 기존 관측 자산 완전 비침습 확인.

**IAM 권한**: 사용자가 CloudShell에서 `dpyb-discovery-dev-bedrock` Role에
`DiscoveryCloudWatchMetricsPolicy`(네임스페이스 `DPYB/Discovery/LLM` 조건부
`cloudwatch:PutMetricData`) 인라인 정책을 직접 등록 완료(기존 `bedrock-invoke` 정책 유지 확인).

**남은 작업**:
- [ ] 커밋 생성 및 push (사용자 승인 대기, `[CLIAR-276]` 태그)
- [ ] dev configmap에 `ENABLE_CLOUDWATCH_METRICS=true` 배포 후 CloudWatch 콘솔에서 실제
      `BedrockCostUSD`/`InputTokens`/`OutputTokens`/`CacheReadTokens`/`SearchCacheHit`/
      `SearchCacheMiss` 메트릭 도착 확인
- [ ] CloudWatch 대시보드 1개 구성(비용 추이, 캐시 히트율)
- [ ] (여유 있을 때, 그래프 완료 후) Task 7: CloudWatch Alarm(예: 시간당 비용 급등) → SNS →
      Lambda(Discord 웹훅). 기존 Grafana→Discord RCA Agent와는 **별개 채널**(다른 웹훅 URL)로
      분리해 알림 출처를 혼동하지 않게 한다
- [ ] Task 8: `ARCHITECTURE.md`에 "독립 CloudWatch LLM 관측(선택적, 기본 OFF)" 서술 추가

**리스크/메모**: CloudWatch 커스텀 메트릭은 소액 비용 발생(메트릭당 월 ~$0.30 + API 호출
요금) — 플래그로 통제. 차원(Dimension)은 `Model`만 사용해 카디널리티를 낮게 유지(세션ID 금지).

---

## [진행 중] CLIAR-281: [오케스트레이터] 추천 에이전트 속도 원인 진단 후 수정

**배경 (2026-09-04)**: CLIAR-278(Sonnet 5 → Haiku 4.5 교체)로 45초 → 12초까지 줄었으나,
사용자가 "사서 에이전트를 합치면 더 줄어들지" 문의. dev 클러스터에서 discovery Pod →
`backend-librarian` Pod 직접 HTTP 실측(콜드스타트 제외 28~30ms)으로 **사서 상담 구간은
이미 무시할 수준**임을 확인해 통합 방향은 폐기했다. 대신 dev 실제 로그(`agent_metrics`)
분석으로 진짜 병목을 특정했다:

- `recommend_books`(추천 에이전트) 도구가 오케스트레이터 전체 시간의 **58~76%**를 차지
  (예: 41.5초 중 23.9초, 47.5초 중 36.2초).
- `recommend_books` 내부에서도 Strands가 재는 LLM 사이클 시간(15~21초)과 실제
  `total_duration_ms`(24~36초) 사이에 **8.7~14.8초의 미계측 간극**이 존재.
- 코드 분석 결과 유력 후보: `_verify_page_counts`가 추천된 도서마다 `backend-book`에
  "제목·저자→ISBN(`by-title-author`)→페이지수(`search?isbn=`)" **2단 순차 HTTP**를
  보내고 있음(권당 왕복 2회, 알라딘 경유라 지연 가능성). 이 구간이 로그에 전혀 안 찍혀
  간극의 정체를 몰랐다.
- 진단을 위해 `recommend_tool.py`의 `recommend()`에 구간별 계측(`agent_creation_ms`,
  `agent_invoke_ms`, `verify_page_counts_ms`)을 이미 추가함(미커밋, 이번 브랜치로 이동).

**Task**:
- [x] Task 1: `recommend_tool.py`에 구간별 `time.perf_counter()` 계측 추가
      (에이전트 생성/`invoke_async`/`_verify_page_counts` 3구간 분리, `log_agent_metrics`의
      `direct_metrics`에 포함). `ruff`/`mypy`/단위 테스트(281건) 통과. PR #52 머지·dev 배포 완료.
- [x] Task 2: dev 배포 후 실제 사용자 추천 요청 로그(`agent_metrics`, phase=`recommend_agent`)
      실측 확인(2026-09-04, 45.9초 요청). 결과: `verify_page_counts_ms`=1.77초(4%, 병목
      아님), `agent_creation_ms`=0.14초(무시), **`agent_invoke_ms`=24.6초(93%, 진짜 범인)**.
      가설(`_verify_page_counts`가 범인)은 반증됨.
- [x] Task 3: `agent_invoke_ms`(24.6초) 내부 분석. `strands_metrics.total_cycles: 3`,
      `search_books` `call_count: 3` 확인 — LLM이 시스템 프롬프트의 "1~2회 이내로
      효율적으로"라는 권장 문구를 지키지 않고 3회 도구 호출 사이클을 돌고 있었다.
      Strands가 재는 순수 사이클 시간(11.9초)과 실제 `agent_invoke_ms`(24.6초) 사이
      12.7초 간극은 Strands SDK 내부(사이클마다 반복되는 Bedrock 크로스리전 오버헤드
      추정)라 완전히 규명하지 못했으나, **사이클 수 자체를 줄이는 것이 간극도 함께
      줄이는 근본 해결**이라고 판단(사이클이 늘수록 간극도 비례해 누적되는 구조).
      더 정밀한 계측(`stream_async` 전환)은 기존 단위 테스트 5건이 mock 방식과 충돌해
      침습성이 커 보류(`invoke_async` 유지).
- [x] Task 4 (근본 수정): `domain/librarian/agent.py`의 CAT/STORK 시스템 프롬프트에서
      "1~2회 이내로 효율적으로 활용"(권장, 강제력 없음)을 "**정확히 1회만** 호출,
      2번째 검색 금지, 주제 단위로 폭넓게 검색해 한 번에 후보 확보"로 명확화.
      `recommend_tool.py`의 사용자 프롬프트에도 "search_books는 정확히 1회만 호출"
      지시를 이중으로 추가(시스템 프롬프트 미준수 방어). 단위 테스트 1건(`invoke_async`
      호출 prompt 문자열 assert) 갱신, `ruff`/`mypy`/`pytest -m "not integration"`
      281건 전체 통과(무회귀).
- [ ] Task 5: dev 배포 후 전후 비교 — 수정 전(`total_cycles: 3`, `search_books call_count: 3`,
      `agent_invoke_ms` ~24.6초) vs 수정 후(목표: `total_cycles` 1~2, `call_count` 1,
      `agent_invoke_ms` 유의미하게 감소) 실측 확인.
- [ ] Task 6: 하네스 문서(`STATE.md`/`DECISIONS.md`) 동기화.

**폐기된 방향**: 사서 에이전트(`backend-librarian`)를 discovery로 통합하는 것 — 실측상
효과가 없어(28ms) 이번 티켓 범위에서 제외. `_verify_page_counts`(backend-book 2단 조회)
최적화도 실측상 4%(1.77초)라 이번 범위에서 후순위로 내림.

---

## [코드 완료 · dev 배포/스크레이핑 확인 대기] 관측 인프라(dont-paw-get/infra) 연동 — dev 환경

브랜치: `관측-인프라-연동` (티켓 없음 — 배포용 임시 작업, 커밋 `[CLIAR-XX]` 태그 생략, 사용자 확정 2026-09-02)

**배경**: infra 저장소에 Prometheus/Grafana/Loki/Tempo + RCA Agent(Grafana 알림 → Discord 원인분석)가 dev 클러스터(`monitoring` ns)에 구축됨. infra의 "HTTP 5xx 에러율" / "p99 레이턴시" 알림이 동작하려면 이 서비스가 Prometheus HTTP 메트릭을 노출하고 ServiceMonitor로 스크레이핑돼야 한다.

**서비스명**: `<SVC>` = `backend-discovery` (메트릭 `application` 태그 = `OTEL_SERVICE_NAME` = 트레이스 `service.name` = k8s 리소스명, 전부 동일).

**구현 완료 (코드 세부는 `.harness/STATE.md`)**:
- Task 1: `prometheus-client` 의존성 추가, `core/metrics.py`(순수 ASGI 미들웨어 + Micrometer 호환 `http_server_requests_seconds` 히스토그램, 버킷 60초까지, `application` 라벨 = `OTEL_SERVICE_NAME`), `main.py`에 미들웨어 + `GET /metrics` 배선.
- Task 2: `k8s/overlays/dev/servicemonitor.yaml`(name `backend-discovery`, `port: http`, `path: /metrics`, `interval: 30s`) + dev kustomization resources 추가. prod overlay 미변경.
- Task 3: `k8s/overlays/dev/configmap-patch.yaml`에 `OTEL_METRICS_EXPORTER=none` / `OTEL_LOGS_EXPORTER=none` 추가.
- Task 4: 변경 없음 (`core/logging.py`가 이미 `trace_id`+`level` 출력).
- Task 5: `core/tracing.py:_EXCLUDED_URLS`에 `metrics` 추가.
- Task 6: **사용자 지시로 보류** — genre classifier 베어 모델 ID는 이번 범위에서 건드리지 않음.
- 검증: `tests/unit/test_metrics.py` 3건 신규, 전체 254건 + `ruff`/`mypy` + `kubectl kustomize k8s/overlays/dev` 통과.

**남은 작업 (dev 배포 후)**:
- [ ] dev 배포 후 `/metrics`가 `http_server_requests_seconds_bucket`/`_count`/`_sum`을 `application="backend-discovery"` 라벨로 노출하는지 확인
- [ ] Prometheus가 ServiceMonitor `backend-discovery`(`dpyb-discovery-dev`)로 실제 타깃을 잡고 스크레이핑하는지 `kubectl`/Prometheus targets에서 확인
- [ ] infra 저장소에 회신: (1) `<SVC>`=`backend-discovery` (2) ServiceMonitor `backend-discovery` / `dpyb-discovery-dev` (3) Micrometer 이름 모방이라 알림 규칙 수정 불필요 — `http_server_requests_seconds_{count,bucket}`, 라벨 `method,uri,status,outcome,application` (4) 스크레이핑 확인 결과
- [ ] (후속 검토) `/metrics`가 Ingress `path: /` 로 외부 노출됨 — dev 한정 수용, 필요 시 ingress 차단 또는 별도 포트 분리

---

## [코드 완료 · 로컬 실측 검증 · dev 배포 대기] 페이지수 2단 조회 + Authorization 패스스루 (CLIAR-237 재수정)

**배경 (2026-09-02~03 실측)**: 사용자가 "페이지수를 못 가져오는 경우"를 제보. dev 실서버에 실제 HTTP 호출로 확인한 결과 두 근본 원인을 확정했다:
1. `by-title-author`와 `search?isbn=` **두 엔드포인트 모두 무인증 호출 시 401**(`UNAUTHORIZED`)을 반환한다. 기존 `fetch_by_title_author`는 Authorization을 안 보내 실서비스에서 항상 401 → `None`.
2. `by-title-author`는 ISBN은 반환하지만 **목록 검색만 수행하여 `totalPages`가 항상 null**이다. 같은 책(사피엔스 9788934972464)이 `search?isbn=`(ISBN 상세 조회)에서는 `totalPages: 648`로 정상 반환됨을 실측 확인. 즉 CLIAR-237 후속에서 ISBN 경로를 버리고 by-title-author로 전환한 것이 페이지수를 주는 쪽을 버린 셈이 됐다.

**해결(A안, 사용자 확정)**: `by-title-author`(제목·저자→ISBN) + `search?isbn=`(ISBN→페이지수) 2단 조회로 두 문제를 모두 우회. Authorization 토큰을 라우터→서비스→도구→클라이언트로 패스스루. 구현 세부는 `.harness/STATE.md` 참고. 실 토큰 실측으로 사피엔스648/백야행592/돈의심리학416/어린왕자136 정상 확보 확인.

**남은 작업**:
- [ ] dev 배포 후 실제 추천 요청으로 `recommended_books[i].page_count`가 채워지는지 확인(로컬 실측은 완료, dev 파이프라인 통합 확인만 남음)

---

## [코드 구현 완료 · dev 실측 대기] CLIAR-244: 도서 추천 카드 장르(16개 표준) 필드 추가

**배경 (2026-09-02, 스크린샷으로 재확인)**: 지금 프론트 상단 칩에 "미스터리"가 이미 표시되고 있으나, 이 값은 `ChatResponse.signals.genre_focus`(`backend-librarian`이 대화 분석으로 자유 판단한 `list[str] | str`, 코드로 확인: `librarian_response.py:58`)로 **16개 표준 `StandardGenre` Enum 매핑을 거치지 않은 값**이다. 사용자 요청: (1) 상단 칩에는 날씨/시간대/분위기만 남기고 장르 칩은 제거, (2) 대신 **각 도서 카드 내부**(저자 옆)에 그 도서의 실제 표준 장르를 표시, (3) "등록하기" 버튼 클릭 시 이 장르 값이 등록 요청 페이로드에 함께 실려야 함 — 즉 표시 이동이 아니라 `RecommendedBookCard`에 구조화 필드로 편입되어야 하는 문제.

**핵심 제약**: 기존 `POST /api/v1/classify-genre`(`GenreClassifierService`)는 CLIAR-235에서 **ISBN 전용**으로 개편되어 title/author 입력을 받지 않는다. 추천 카드(`RecommendedBookCard`)는 Tavily 웹검색 기반이라 ISBN을 안정적으로 확보하기 어렵다. 따라서 classify-genre 엔드포인트를 그대로 재호출하는 방식은 불가능하고, **추천 에이전트가 도서를 생성하는 시점에 장르까지 함께 판단하게** 해야 한다.

**구현 완료 세부**: `.harness/STATE.md` 참고.

**남은 작업**:
- [ ] dev 배포 후 실제 추천 요청으로 `recommended_books[i].genre` 필드가 채워지는지 확인
- [ ] 프론트 전달 사항 정리 완료 (`.harness/HANDOFF.md` 참고)

---

## [진행 중 · 원인 미해결] dev 환경 504 Gateway Timeout (CloudFront) — 도서 추천 응답 지연

**배경 (2026-09-02 실측)**: 사용자가 dev(CloudFront `d1wab52ln5by5k.cloudfront.net`)에서 도서 추천 요청 시 브라우저에서 `504 Gateway Timeout`(정확히 30.02초)을 다수 재현. 응답 헤더에 `via: CloudFront`, `x-cache: Error from cloudfront`가 확인되어 **CloudFront가 오리진(ALB) 응답을 기다리다 자체적으로 타임아웃**시킨 것으로 확정(백엔드가 아니라 CloudFront가 504를 만들어냄).

**로그로 확인된 실측 사실**:
- `kubectl logs`로 확인한 실제 오케스트레이터 요청 소요시간: **32초, 39초, 40.6초, 41.3초** (모두 200 성공 응답이었으나 소요시간이 김).
- 병목은 `recommend_books`(하위 추천 에이전트) 도구 하나가 17~26초를 씀(오케스트레이터 총 시간의 절반 이상).
- `strands_metrics.total_duration`(LLM 사이클 실행시간 합산)은 6~13초인데, 우리가 감싼 wall-clock(`total_duration_ms`)은 그보다 10초 이상 더 큼 — Strands가 측정하지 않는 구간(에이전트/모델 객체 생성, Bedrock 크로스리전 프로필 자체의 네트워크 latency 등)에서 시간이 추가로 소모되는 것으로 추정되나 **정확한 원인 미확인**.
- 사용자가 CloudFront의 Origin Response Timeout을 30초 → 60초로 변경한 뒤에도 504가 재현됨. 이후 CloudFront distribution이 "Deploying" 상태였을 가능성을 짚었고, 사용자가 "넘어온다"고 확인(재현 안 됨)해 이번 세션은 일단 완화된 것으로 보고 종료. **다만 재현이 사라진 게 설정 전파 완료 때문인지, 우연히 짧게 끝난 요청이었는지 확정 검증은 안 됨.**

**다음 세션이 확인/진행할 것**:
- [ ] CloudFront Origin Response Timeout이 실제로 60초로 "Deployed" 상태인지 재확인, 그리고 60초보다 오래 걸리는 요청(위 실측상 40초대는 자주 나옴)이 안전한지 몇 차례 더 재현 테스트
- [ ] ALB idle timeout도 확인 필요(`k8s/base/ingress.yaml`에 명시적 어노테이션 없어 기본값 60초로 추정 — CloudFront보다 먼저 끊길 가능성은 낮으나 미확인)
- [ ] **근본 해결(권장)**: `recommend_books` 도구의 17~26초 소요 자체를 줄이는 작업. CLIAR-158 Task 3~5(캐싱/reasoning 실측), 백로그의 "직결 스트리밍" 항목과 연계 검토. 지금처럼 타임아웃만 늘리는 건 임시방편이며, 요청이 더 길어지면(예: 5권 추천) 다시 504가 날 수 있음
- [ ] 위 "총 시간 - Strands 사이클 시간 = 10초 이상 간극"의 정확한 원인 규명(에이전트 생성 오버헤드 vs Bedrock 네트워크 latency vs 다른 요인) — 세부 계측 지점 추가하여 실측

---

## 진행 순서 (2026-09-01 확정)

CLIAR-171과 CLIAR-216이 `src/discovery/domain/orchestrator/agent.py`의 같은 페르소나 프롬프트 상수를 건드리므로 병행하지 않는다.
프롬프트를 **축소하는 작업(CLIAR-171)이 확장하는 작업(CLIAR-216)보다 먼저**다.

| 순서 | 티켓 | 범위 | 선행 조건 |
| --- | --- | --- | --- |
| 1 | **CLIAR-158** | ✅ **완료·develop 머지** (Task 1·2 코드 구현 완료 및 머지. Task 3~5는 dev 실측 필요 — 별도 스파이크로 처리) | 없음 |
| 2 | **CLIAR-215** (QA기반 최적화a) | ✅ **완료** — Task 1(실측 러너 및 실측 완료)·Task 2(인증 Presence Check, 401, ADR 0007)·Task 3(위기 109 핫라인 게이트)·Task 4(공백 422 및 입력 게이트)·Task 5(P1 회귀 확인)·Task 6(단위 테스트 196건 통과) | 없음 |
| 3 | **CLIAR-171** | ✅ **완료** — Task 1-0(search_books 페이로드 축소) + Task 1(오케스트레이터 카드 재생성 제거 및 splice 결합) + Task 2(리전/프로필 비교) + Task 3(추론 파라미터 튜닝) | CLIAR-215 완료 |
| 4 | **CLIAR-229** | ✅ **완료** — 도서 추천 카드 구조화 필드(`RecommendedBookCard`, 저자/쪽수 분리) + 출력 HTML 태그 노출 방어(`sanitize_html_tags`) | CLIAR-171 완료 |
| 5 | **CLIAR-235** | ✅ **완료** — 도서 장르 분류 API의 ISBN 단일 요청 필드 개편 (title/author/raw_category 제거 및 ISBN 전용 분류로 간소화) | 없음 |
| 6 | **CLIAR-236** | ✅ **완료** — 고도화 후 자잘한 버그 수정: Claude Sonnet 5 도구 호출 포맷 붕괴(assistant message prefill ValidationException) 방어 재시도 로직 (`is_tool_call_format_error`, chat/stream_chat 1회 재시도 배선, 단위 테스트 6건) | CLIAR-229 완료 |
| 7 | **CLIAR-237** | ✅ **완료** — 추천 도서 페이지수를 `RecommendBooksTool` 내부에서 `backend-book` 알라딘 실조회(`GET /api/v1/books/search?isbn=...`)로 검증. ISBN 내부 주석(`<!-- isbn: ... -->`) 파싱·제거, `BookMetadataClient` 신설, 단위 테스트 19건 | CLIAR-236 완료 |
| 8 | **CLIAR-216** (QA기반 최적화b) | ✅ **완료** — 공통 가드레일(`SHARED_GUARDRAILS`) 모듈화 리팩터링 + 추천 에이전트 환각 방지(9번 규칙) + 감정 공감 톤 + 범위 밖 질문 차단 가드레일. 단위 테스트 262건 100% 통과 | CLIAR-237 완료 |
| 9 | **CLIAR-257** (추천 결과 기억하기) | 🔄 **다음 착수 대상** — 프론트 `sessionStorage`/전역 상태 캐싱(단기 우선), 백엔드 히스토리 영속화(중장기)는 `.harness/BACKLOG.md` 참고 | CLIAR-216 완료 |

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

### 프론트엔드 조치 요청 사항 (별도 전달 항목)

- **디바이스 위치 권한 비동기 전송 조치 (CLIAR-216 후속)**:
  - **현상**: 브라우저 `navigator.geolocation.getCurrentPosition()` 권한 팝업 대기로 인해 백엔드 HTTP 요청 자체가 지연/미발생.
  - **프론트 조치 예시**: 위치 권한 응답을 기다리지 않고 즉시 `latitude=null, longitude=null`로 대화 요청을 선제 전송 (백엔드가 기본 서울 날씨로 즉시 응답)하거나, geolocation 조회에 짧은 타임아웃 옵션을 적용.

---

### 백로그로 이관 (이번 범위 제외)

- **직결 스트리밍(Bypass) 아키텍처 변경**: Agent-as-a-Tool의 `str` 반환 계약상 불가. 의도 분기를 서비스 레이어 코드로 이관해야 하며 CLIAR-208/213의 프롬프트 분기 재구현 + `switch_to`/`signals`/`library_books` 배선 전면 영향. CLIAR-171 Task 1의 효과 측정 후 필요성 재판단
- **Early Stop(권수 충족 시 조기 중단)**: 중단할 스트림이 없고 `truncate_books_by_count`와 충돌. 기본 2권 + 수량 엄수 프롬프트로 기대 이득 이미 회수됨
- **`signals`를 헤더에서 SSE 첫 이벤트로 이관**: `get_initial_meta`의 TTFB 하한을 구조적으로 없애는 방법이지만 ADR 0003/0005 계약 변경 + 프론트 동반 수정 필요. CLIAR-158 Task 2로 실질 해소되는지 먼저 확인
- **Bedrock Guardrails 검토**: 지연을 **증가**시키므로 레이턴시 최적화 티켓과 상충. 내용상 CLIAR-215 Task 3과 중복이므로 그쪽에서 "코드 게이트 vs Guardrails" 비교로 다룬다
