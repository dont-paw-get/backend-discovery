# PLAN — backend-discovery

## [진행 예정] Bedrock & 에이전트 성능 고도화 3단계 (관측 ➔ 직결 스트리밍 ➔ 인프라 최적화)

**목표:**  
"관측(숫자로 병목 파악) ➔ 아키텍처 개선(직결 스트리밍) ➔ 인프라 최적화(AWS Bedrock Latency-Optimized Inference)"의 계층적 스토리라인에 따라 체계적으로 레이턴시를 단축하고 안정성을 확보한다.

---

### 단계별 Task 체크리스트

#### Phase 1: 관측성 구축 (Observability & Latency Breakdown)
> **목적:** 각 단계별(오케스트레이터 첫 추론, 도구 호출, 하위 에이전트 추론, Tavily/서재 API 호출 등) 지연시간을 수치로 정확히 측정·로깅

- [ ] **Task 1-1: 레이턴시 계측 타이머 및 구조화 로거/컨텍스트 설계**
  - 스트리밍 세션 시작부터 첫 토큰 방출(TTFT), 각 도구 실행 시간, 하위 에이전트 스트리밍 소요 시간을 추적하는 경량 프로파일러 유틸리티 구축
- [ ] **Task 1-2: `OrchestratorService` & `stream_chat` 구간별 메트릭 로깅**
  - 오케스트레이터 의도 분류 소요 시간
  - 도구별(`SearchMyLibraryTool`, `RecommendBooksTool`, `ConsultLibrarianTool`) I/O 및 내부 LLM 추론 시간
  - 전체 요청 처리 완료 시간(Total Latency)
- [ ] **Task 1-3: 현재 베이스라인 지연시간 실측 및 구간별 병목 기록**
  - 서재 조회, 도서 추천, 사서 상담 각각의 시나리오별 실측 지표 수집 및 분석

---

#### Phase 2: 아키텍처 레벨 최적화 (직결 스트리밍 파이프라인 / Direct Streaming)
> **목적:** Phase 1에서 확인된 최대 병목(하위 에이전트가 완료될 때까지 상위 오케스트레이터가 대기 후 재포장하는 2중 버퍼링)을 제거하여 체감 응답 속도 혁신

- [ ] **Task 2-1: 하위 추천/사서 스트림의 직결 바이패스(Direct Pass-through) 파이프라인 설계**
  - 오케스트레이터가 도구 호출(`recommend_books` 등)을 결정하는 즉시, 하위 에이전트의 생성 스트림 델타를 클라이언트에 실시간으로 직결 파이핑
  - 상위 모델의 불필요한 후속 재포장 추론 턴 제거 (1턴 절약으로 2~3초 단축)
- [ ] **Task 2-2: 사서 어조 및 도서 마크다운 카드 일체화 유지**
  - 하위 에이전트 프롬프트에서 이미 사서 페르소나(블루/슈빌)와 `### 📖` 마크다운 카드를 완성하여 출력하므로, 계약 파손 없이 직결 전달
- [ ] **Task 2-3: 단위/통합 테스트 작성 및 개선 후 TTFT/Total Latency 실측 비교**

---

#### Phase 3: 인프라 레벨 최적화 (AWS Bedrock Latency-Optimized Inference 조사 및 적용)
> **목적:** 소프트웨어 레벨 최적화 완료 후, 남는 물리적 모델 추론 지연을 AWS 인프라 최적화 기능으로 단축

- [ ] **Task 3-1: AWS Bedrock Latency-Optimized Routing / Inference Profile 지원 현황 조사**
  - 대상 모델(Claude 3.5 Sonnet, Claude 3 Haiku) 및 리전(`ap-northeast-2`, `us-east-1` 등)별 지연시간 최적화 추론 프로필 지원 여부 조사
  - 조사 결과를 `.harness/research/` 또는 ADR에 문서화
- [ ] **Task 3-2: (지원 시) Bedrock 클라이언트 및 환경변수 설정 반영**
  - 지연시간 최적화 프로필 ARN/Model ID 주입 및 스트리밍 레이턴시 비교
  - 미지원 시 한계 및 대체 방안(예: 글로벌 CRIS 프로필 활용 현황 점검) 문서화 마감

---

### [참고] 보류/후속 백로그
- 프롬프트 캐싱 실측 및 미세 튜닝 (현재 코드에 적용되어 있으므로 현상 유지)
- Pydantic Structured Output 전면 전환 (설계 비용이 큰 별도 트랙)
- 병렬 도구 호출 (도구 수 증가 시 재검토)

