# AWS CloudWatch LLM 관측 대시보드 구성 가이드 (CLIAR-276)

본 문서는 `backend-discovery`의 LLM 파이프라인(Bedrock) 비용·토큰·지연시간·캐시 지표를 AWS CloudWatch 커스텀 메트릭으로 수집하고, 이를 시각화하는 대시보드 구성 가이드입니다.

---

## 1. 📌 개요 및 목적

* **목적**:
  * **FinOps (비용 최적화)**: 모델별 실시간 USD 비용 추적 및 프롬프트 캐싱을 통한 절감액 정량화
  * **체감 성능 관측 (SLA)**: 사용자 체감 E2E 지연시간(`RequestLatencyMs`) 및 스트리밍 첫 글자 도착 시간(`TimeToFirstByteMs`, TTFT) p50/p90/p99 모니터링
  * **Zero-Overhead & Zero-Data-Leak**: 외부 SaaS(Langfuse 등) 없이 AWS 네이티브 CloudWatch와 IRSA IAM 권한을 활용한 안전한 격리 관측 스택
* **활성화 방법**:
  * `ENABLE_CLOUDWATCH_METRICS=true` (기본값: `false`, 비활성화 시 어떠한 AWS 호출도 없는 완전한 no-op 동작)

---

## 2. 📊 CloudWatch 지표 명세

* **Namespace**: `DPYB/Discovery/LLM`
* **Dimensions**: `Model` (단일 차원으로 카디널리티 및 커스텀 메트릭 비용 최소화)
  * 예: `global.anthropic.claude-haiku-4-5-20251001-v1:0` (현재 운영 모델)
  * 예: `global.anthropic.claude-sonnet-5` (이전 모델)

### 수집 메트릭 목록

| 메트릭 이름 | 단위 (Unit) | 주요 통계 (Statistic) | 설명 |
| :--- | :--- | :--- | :--- |
| `RequestLatencyMs` | Milliseconds | Average, p50, p90, p99 | 요청 전체 소요 시간 (안전/입력 게이트 조기 반환 건 제외) |
| `TimeToFirstByteMs` | Milliseconds | Average, p50, p90 | 스트리밍 응답(`stream_chat`) 첫 번째 텍스트 청크 수신 시간 (TTFT) |
| `BedrockCostUSD` | None | Sum | 정가 단가표 기반 요청당 추정 비용(USD) |
| `InputTokens` | Count | Sum | Bedrock 모델 입력 토큰 수 |
| `OutputTokens` | Count | Sum | Bedrock 모델 출력 생성 토큰 수 |
| `CacheReadTokens` | Count | Sum | 프롬프트 캐시에서 읽어온 토큰 수 (비용 90% 절감 영역) |
| `CacheWriteTokens` | Count | Sum | 프롬프트 캐시에 신규 적재된 토큰 수 |
| `SearchCacheHit` | Count | Sum | Tavily 검색 결과 Redis 캐시 히트 횟수 |
| `SearchCacheMiss` | Count | Sum | Tavily 검색 결과 Redis 캐시 미스 (외부 API 호출) 횟수 |

---

## 3. 🚀 선언형 IaC 배포 (AWS CloudFormation 1-Step)

본 대시보드는 재현 가능한 선언형 IaC 템플릿(`cloudwatch-dashboard-stack.yaml`)으로 버전 관리됩니다. 콘솔에서 일일이 위젯을 생성할 필요 없이 AWS CloudShell 또는 터미널에서 아래 단 1줄의 명령어로 자동 배포할 수 있습니다.

```bash
# AWS CloudShell 또는 로컬 터미널에서 실행
aws cloudformation deploy \
  --template-file docs/observability/cloudwatch-dashboard-stack.yaml \
  --stack-name dpyb-discovery-cloudwatch-dashboard \
  --region ap-northeast-2
```

> **배포 후 확인**:
> AWS 콘솔 ➔ **CloudWatch** ➔ **Dashboards** ➔ **`DPYB-Discovery-LLM-Dashboard`** 클릭 시 아래 4개 위젯이 즉시 렌더링됩니다.

---

## 4. 🖥️ 대시보드 위젯 명세 및 메트릭 구성

대시보드는 아래 4개의 핵심 위젯으로 구성되어 있습니다:

### 위젯 1: [성능] 체감 지연시간 & TTFT 추이 (Line Chart)
* **메트릭**:
  * `RequestLatencyMs` (Model = Haiku 4.5) ➔ Statistic: `p90`
  * `RequestLatencyMs` (Model = Haiku 4.5) ➔ Statistic: `Average`
  * `TimeToFirstByteMs` (Model = Haiku 4.5) ➔ Statistic: `p90`
  * `TimeToFirstByteMs` (Model = Haiku 4.5) ➔ Statistic: `Average`
* **Period**: 1 minute 또는 5 minutes
* **목적**: 사용자의 대기 체감 지연시간 변화를 실시간으로 추적하고 이상치(Spike) 감지

### 위젯 2: [FinOps] 실시간 Bedrock 누적 비용 (Number / Stacked Area)
* **메트릭**:
  * `BedrockCostUSD` (Model = Haiku 4.5) ➔ Statistic: `Sum`
* **Period**: 1 hour 또는 1 day
* **목적**: 일일/시간당 발생 비용 추이를 추적하고 예산 초과 방지

### 위젯 3: [효율] 토큰 사용량 및 프롬프트 캐시 절감 (Stacked Bar / Line)
* **메트릭**:
  * `InputTokens` ➔ Statistic: `Sum`
  * `OutputTokens` ➔ Statistic: `Sum`
  * `CacheReadTokens` ➔ Statistic: `Sum`
* **Metric Math (캐시 절감률 계산식)**:
  * ID `e1`: `m_cache_read / (m_input + m_cache_read) * 100`
  * 라벨: `Prompt Cache Hit Ratio (%)`
* **목적**: 프롬프트 캐싱 활성화에 따른 실질적인 입력 토큰 절감 효과 검증

### 위젯 4: [도구] Tavily 도서 검색 캐시 히트율 (Pie Chart / Number)
* **메트릭**:
  * `SearchCacheHit` ➔ Statistic: `Sum`
  * `SearchCacheMiss` ➔ Statistic: `Sum`
* **Metric Math (검색 캐시 히트율)**:
  * ID `e2`: `m_hit / (m_hit + m_miss) * 100`
  * 라벨: `Search Cache Hit Ratio (%)`
* **목적**: 동일/유사 키워드 재검색 시 Redis 캐시 재사용률 모니터링

---

## 4. 💡 발표 및 성과 보고용 팁 (Before vs After 비교)

과거 Sonnet 5 사용 시점의 메트릭이 남아있다면, 동일 위젯에 두 모델 라인을 겹쳐 배치하여 **성능·비용 최적화 성과**를 정량적으로 증명할 수 있습니다:

1. **지연시간 단축 증명**:
   * Sonnet 5 p90 TTFT (~9.2초) ➔ Haiku 4.5 p90 TTFT (~1.6초) **약 82% 단축**
2. **비용 절감 증명**:
   * Sonnet 5 (입력 $3 / 출력 $15) 대비 Haiku 4.5 (입력 $1 / 출력 $5) 도입으로 **토큰당 비용 약 67% 절감**

---

## 5. 🛠️ 점검 및 트러블슈팅

1. **지표가 콘솔에 나타나지 않는 경우**:
   * K8s ConfigMap에 `ENABLE_CLOUDWATCH_METRICS: "true"`가 적용되어 있는지 확인합니다.
   * 파드 IRSA Role(`dpyb-discovery-dev-bedrock`)에 `cloudwatch:PutMetricData` 권한 정책(`DiscoveryCloudWatchMetricsPolicy`)이 부여되어 있는지 확인합니다.
2. **단순 인사나 안전 게이트 발화 시 지표가 안 찍히는 이유**:
   * 위기 대응(`evaluate_safety_gate`) 및 자모/숫자 등 단순 입력 필터(`evaluate_input_gate`)로 즉시 반환된 요청은 **p50/p90 지연시간 왜곡을 방지하기 위해 의도적으로 메트릭 발행 대상에서 제외**되어 있습니다 (정상 동작).
3. **토큰/캐시는 뜨는데 성능(지연시간)과 과금 데이터가 안 뜨는 이유**:
   * **성능 지표(`RequestLatencyMs`, `TimeToFirstByteMs`)**: 레이턴시를 발행하는 핵심 코드는 **PR #65**에 구현되어 있습니다. 따라서 PR #65가 `develop`에 머지되고 ArgoCD / K8s dev 환경에 새 이미지로 배포된 이후의 챗봇 대화부터 CloudWatch에 실데이터가 적재되기 시작합니다.
   * **과금 지표(`BedrockCostUSD`)**: PR #65 배포 이미지와 함께 요청당 추정 USD 비용이 함께 계산되어 발행됩니다.
4. **그래프가 지저분하게 튀거나 보기 어려운 경우 (시각화 튜닝 팁)**:
   * **Period(간격) 조정**: 요청이 간헐적인 개발 환경에서는 Period를 1분으로 두면 선이 끊기거나 뾰족하게 튑니다. Period를 **`5 minutes` 또는 `15 minutes`**로 설정하면 선이 부드럽게 이어집니다.
   * **통계 방식(Statistic) 변경**:
     * 토큰 수 및 비용: `Average` 대신 **`Sum`**으로 설정해야 시간 구간별 총 사용량이 정확하고 깔끔하게 집계됩니다.
     * 지연시간: `Maximum` 대신 **`p90`** 또는 **`Average`**를 메인으로 두어야 일시적인 네트워크 튐 현상에 영향받지 않습니다.
   * **위젯 타입 변경**:
     * Tavily 검색 캐시(Hit vs Miss)나 비용은 꺾은선 그래프보다 **Stacked Bar(누적 막대)** 또는 **Number(단일 숫자 카드)** 위젯으로 설정하면 훨씬 직관적이고 깔끔합니다.
