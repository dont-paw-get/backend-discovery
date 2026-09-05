# BACKLOG — backend-discovery

지금 하지 않지만 나중에 할 것.

- [ ] **원격 사서 에이전트(`backend-librarian`) Bedrock 모델 확인 및 동기화** (2026-09-05) — `backend-discovery`는 ConfigMap/코드를 Haiku 4.5로 맞췄으나, dev overlay의 `LIBRARIAN_AGENT_URL`을 통해 호출되는 원격 사서 서비스(`backend-librarian`)가 실제로 어떤 모델을 쓰는지, Haiku 4.5 전환이 필요한지는 해당 레포지토리(`dont-paw-get/backend-librarian`) 확인 및 팀 조율 필요 (`backend-discovery` 레포 범위 밖).
- [ ] **`_replace_page_count_for_title`(`recommend_tool.py`) 문자열 끝 미매치 버그** (2026-09-04 발견, CLIAR-282 병렬화 테스트 작성 중 재현) — 도서 블록이 마크다운 문자열의 맨 끝이고 뒤에 개행이 없으면(예: `"### 📖 제목\n- **저자**: 이름 (약 700쪽)"`로 끝) 정규식 `(.+?)(\s*\n)`이 후행 개행을 요구해 매치가 안 되고, 검증된 페이지수로 교체되지 않는다. 실제 LLM 생성 마크다운은 저자 줄 뒤에 추천 이유 등 텍스트가 항상 이어져 지금까지 드러나지 않았을 가능성. 재현: `_replace_page_count_for_title("### 📖 제목\n- **저자**: 이름 (약 700쪽)", "제목", 784)`가 원본을 그대로 반환. 수정 시 `_upsert_genre_for_title`도 동일한 문자열 끝 케이스가 있는지 함께 확인 필요.
- [ ] **도서 등록 후 추천 결과 유지 및 세션 히스토리 영속화 (방향 확정, 착수 대기)**:
  - **현상**: 추천 도서 1권 이상을 받고 [등록하기] 화면으로 이동하거나 취소 복귀 시, 대화창 상태가 소실되어 AI에게 20~40초씩 걸려 다시 검색해야 하는 UX 불편.
  - **단기 권장 (프론트엔드)**: `RegisterBook` 라우팅 이동 시 `sessionStorage` 또는 전역 상태에 대화 상태/메시지를 보존하여 복귀 시 레이턴시 0ms로 즉시 복원 (다른 작업 완료 후 진행).
  - **중장기 확장 (백엔드)**: 브라우저 새로고침/재접속 영속성 요구 시 (a) `GET /api/v1/chat/history` 조회 엔드포인트 신설, (b) `ChatSessionStore.append_turn` 세션 턴 스키마에 구조화 필드(`recommended_books`, `library_books`, `switch_to`, `signals`) 저장 확장, (c) 스트리밍 제너레이터 종료 시점에 구조화 카드 파싱 및 저장 배선을 세트로 구현하여 CLIAR-229 회귀 방지.
- [ ] **B안: `by-title-author`가 `totalPages`를 직접 채우도록 backend-book 개선 요청** — 현재 이 엔드포인트는 ISBN은 주지만 목록 검색만 하여 `totalPages`가 항상 null이라, discovery가 "by-title-author→ISBN→search?isbn=" 2단 조회(권당 HTTP 2회)로 우회한다(2026-09-03 A안 구현·실측 완료). 팀원이 `by-title-author` 내부에서 ISBN 상세 조회(알라딘 ItemLookup)까지 태워 `totalPages`를 채워주면 discovery의 2단 조회를 1단으로 되돌릴 수 있다(`fetch_by_title_author`는 이미 `totalPages`가 직접 오면 재조회를 생략하도록 구현되어 있어, backend-book 수정만으로 자동 최적화됨). 레이턴시·호출량 절감 목적. 급하지 않음(A안으로 기능은 이미 정상 동작).
- [ ] **이슈 2(프론트): 추천 카드 장르를 저자 칩 옆에 카드형(div)으로 렌더링** — 백엔드는 `ChatResponse.recommended_books[i].genre`(16개 표준 `StandardGenre` Enum)를 동기 `chat` 응답에 이미 구조화 필드로 내려주고 있다(CLIAR-244, 파서·카드 조립 검증 완료). 현재 프론트(`my-reading-room`)는 이 필드를 안 쓰고 `message` 마크다운의 `- **장르**:` 라인을 그대로 `<li>`로 렌더링 중이라 저자 칩과 포맷이 다르다. 프론트 `BookCardView`(MarkdownRenderer)가 `recommended_books[i].genre`를 읽어 저자 칩과 동일한 칩/카드 스타일로 저자 옆에 렌더링하도록 수정 필요(방향 1 확정). **백엔드 작업 아님 — 프론트 담당 전달 사항.**
- [x] **사서 전환(`switch_to`) 후 추천 미연계 이슈 조사 및 종결** (2026-09-02) — dev 환경 실측 결과 3가지 호출 방식(동기+명시적 librarian_id, 동기+세션 메타 의존, 스트리밍+세션 메타 의존) 모두 정상적으로 사서 전환 후 추천까지 완결됨을 확인(재현 불가). 백엔드 결함이 아니며 프론트엔드 세션 유지 또는 일시적 포맷 문제로 판단되어 백엔드 수정 대상에서 제외 및 종결 처리.
- [ ] **CLIAR-215 QA 케이스 중 서재 API 연동 항목(라우팅-서재검색, signals-날씨반영 등 내 서재 연계 추천) 재검증** — 로컬 검증 환경에는 유효한 JWT를 발급받을 방법이 없어 `qa_runner.py`가 쓰는 임의 토큰(`test-token`)도 `backend-book`이 401로 처리한다(2026-09-02 확인, 이는 CLIAR-215 Task 2에서 구현한 401 전달 로직이 정상 동작하는 증거이지 결함이 아님). 실제 프론트엔드 로그인 세션의 진짜 JWT 또는 `backend-book` 팀이 발급한 유효 토큰으로 dev 환경에서 재검증 필요.
- [ ] Bedrock 모델 가용성 — Haiku 4.5/Sonnet 4 이상은 `kosa-edu-region-pol`로 전
  리전 차단 확인. Claude 3 Haiku, Claude 3.5 Sonnet은 사용 가능 확인됨. 현재
  기본값은 Haiku, 필요 시 Sonnet 3.5로 특정 기능 업그레이드 검토.
- [ ] `search_vector`(tsvector)가 `simple` config를 사용해 한글 조사가 붙은 단어(예: "위로가")가 그 자체로 하나의 lexeme이 되어 정확한 형태로만 매칭된다. 한국어 형태소 분석기(예: PostgreSQL 확장 `pg_bigm`, 또는 외부 mecab 기반 토크나이저)를 검토해 검색 품질을 개선해야 한다. 지금은 GIN 인덱스·하이브리드 검색 인프라 자체의 동작 검증이 목적이라 `simple`로 충분하지만, 실사용 단계에서는 재검토 필요.
- [ ] Bedrock 실연동 — Mock을 실제 `BedrockRuntimeClient`로 교체. 임베딩 차원 1536 재검증 필요
- [ ] 임베딩 모델 변경 시 `vector(1536)` 컬럼 마이그레이션 전략 수립 (재임베딩 배치 포함)
- [ ] `/internal/*` 인증을 공유 시크릿 → mTLS 또는 VPC 내부 제한으로 승격
- [ ] Basic API → Discovery 동기화 실패 시 재시도/DLQ 설계 (현재는 HTTP 단건 동기 호출)
- [ ] HNSW 파라미터(`m`, `ef_construction`, `ef_search`) 실데이터 기반 튜닝
- [ ] 대화 세션 요약 압축 — 토큰 한도 초과 시 오래된 턴 요약 전략
- [ ] CI 워크플로우에 ruff/mypy/pytest(unit+integration) 추가
- [ ] 추천 에이전트 번역 지침(시스템 프롬프트) 적용 후에도 해외 도서 원문(일본어/영어 등)이 마크다운 응답에 그대로 섞여 나오는 사례가 실사용에서 관찰되면, post_processor.py와 분리된 별도 모듈(예: translation_fallback.py)에 비한글 패턴 감지 + Haiku 3 단발 호출 후처리 함수(translate_if_needed)를 추가 검토. 번역 전용 에이전트를 도구(Tool)로 등록하는 방식은 기각됨(판단 자체가 추론 비용이라 오히려 레이턴시/신뢰도 손해).
- [ ] Agents-as-Tools 리팩터링, 사서 연동, ArgoCD 배포 확정 후 `docs/api/openapi.yaml`을 최신 상태로 갱신하고 프론트 담당자에게 공유. 프론트가 axios 클라이언트를 서버별로 작성할 수 있게 엔드포인트/스키마/인증 헤더/CORS 설정을 명확히 문서화.
- [x] Bedrock 추천/오케스트레이터 모델을 Claude 3.5 Sonnet v1(`anthropic.claude-3-5-sonnet-20240620-v1:0`, `ap-northeast-2`)으로 업그레이드 완료 (2026-08-27). 실측 TTFT 617ms, 사서 에이전트와 버전 통일.
- [ ] 최신 CRIS Reasoning 모델들(Sonnet 4/4.5/5, Opus 5 등)은 reasoning 지연(TTFT 1.7~2.4초)으로 실시간 챗봇에는 부적합하나, 향후 스트리밍이 필요 없는 비실시간 작업(예: `POST /api/v1/classify-genre`의 난해한 장르 분류, OCR 서지 오탈자 정밀 보정, 대량 오프라인 배치)의 전용 모델로 활용 검토.
- [ ] 로컬 페르소나 fallback 엔진(`evaluate_local_persona_response`)의 상대 사서 호출 판단 휴리스틱(`_is_calling_librarian`의 15자 이하 짧은 문장 조건) 실사용 오탐(False Positive) 모니터링 및 필요 시 서술어 기반 정밀화 검토.


## 학습/고도화 트랙 (2026-08-28 확정, CLIAR-111 구현·테스트 완료 후 착수)

담당자(에이전트 파트) 개인 학습 목적. 두 트랙으로 분리 — 같은 "속도 개선"이라도 Strands
SDK 레벨 변경과 Bedrock 인프라 레벨 변경은 성격이 달라 별도로 진행한다.

### 트랙 A — Strands SDK 관점 (에이전트 실행 구조)
1. **Observability (트레이싱/메트릭)** — 우선순위 1위, 개인 학습 희망 방향과 일치.
   `AgentResult.metrics`/`traces` 로깅부터 시작해 OpenTelemetry 계측(OTEL Collector →
   CloudWatch/X-Ray 연동까지 확장 가능). 지금 이 레포는 구조적 로깅이 전혀 없어
   "오케스트레이터가 왜 이 도구를 선택했는지", "어느 구간이 느린지"를 볼 방법이 없음
   (기존 "관측성" 항목과 통합). 이후 트랙의 모든 최적화를 숫자로 검증하는 전제 조건이라
   반드시 먼저 진행한다.
2. **직결 스트리밍 파이프라인 (Direct Streaming Pipeline)** — 우선순위 2위.
   지금 `orchestrator_service.py`는 하위 도구(`recommend_books`/`consult_librarian`)가
   완전히 끝난 뒤에야 오케스트레이터가 재생성을 시작하는 2단 구조라 체감 지연이 크다.
   하위 에이전트 토큰을 직접 클라이언트로 중계하고 `### 📖` N+1번째 감지 시 조기 중단
   (Early Stop)하는 방식으로 전환. 1번(트레이싱)으로 병목 구간을 실측한 뒤 착수해야
   효과를 개선 전/후로 비교할 수 있음. `PLAN.md` "대기 과제"의 기존 항목과 동일.

### 트랙 B — Bedrock 관점 (모델 인프라)
1. **Latency-Optimized Inference** — ap-northeast-2 리전 및 현재 사용 모델(Claude 3.5
   Sonnet)의 지원 여부부터 조사. 지원 안 되면 적용까지는 못 가더라도 리전별 기능
   가용성을 확인하는 것 자체가 유효한 학습. 목표는 "조사 후 가능하면 적용"으로 설정
   (무조건 적용을 목표로 잡지 않음).
2. **Prompt Caching 실측/튜닝** — `CacheConfig(strategy="auto")`가 이미 켜져 있지만
   캐시 히트/미스를 관측한 적이 없음. 시스템 프롬프트(`ORCHESTRATOR_SYSTEM_PROMPT`,
   `LIBRARIAN_SYSTEM_PROMPT`)가 모델별 캐시 최소 토큰 기준(Claude 계열 통상
   1,024~4,096 토큰)을 넘는지 확인하고, 캐시 TTL(통상 5분)과 대화 세션 TTL(1시간)의
   불일치가 실제 캐시 효율에 영향을 주는지 검증.
3. **모델 가용성/파라미터 조사** — 리전별 모델 카탈로그, Converse API 추론 파라미터
   (`temperature`, `topP` 등) 튜닝. 위 "Bedrock 모델 가용성"/"CRIS Reasoning 모델" 기존
   항목과 연계.
4. **Guardrails 조사** — 현재 전혀 미사용. 사서/추천 에이전트 응답에 콘텐츠 필터링을
   적용할 수 있는 지점인지 조사.
5. **AgentCore 조사** — 지금은 Strands 에이전트를 FastAPI 프로세스 안에서 직접 구동.
   Bedrock AgentCore로 옮기면 에이전트 배포/스케일링/세션 관리를 Bedrock 인프라
   레벨에서 관리하는 방식을 학습할 수 있음 (아키텍처 전환 여부는 조사 후 별도 결정).