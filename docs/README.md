# docs — backend-discovery 기술 문서 종합 색인

본 디렉토리는 `backend-discovery` 마이크로서비스의 아키텍처, API 계약, 핵심 도메인 기능, 관측성, 보안 및 AWS 선언형 IaC 문서들을 통합 관리합니다.

---

## 📂 문서 구성도

```text
docs/
├── README.md                              # [본 문서] 전체 기술 문서 종합 인덱스
├── api/                                   # API wire 계약 단일 소유 디렉토리
│   ├── README.md                          # API 문서 사용법 및 스펙 검증 가이드
│   ├── openapi.yaml                       # OpenAPI 3.0 공식 계약 명세서
│   └── decisions/                         # API 아키텍처 결정 기록 (ADR)
├── features/                              # 핵심 도메인 비즈니스 기능 상세 가이드
│   ├── aladin-book-verification.md        # 알라딘 서지 검증 & 쪽수 실조회 2단 파이프라인
│   ├── multi-tier-safety-and-fallback.md  # 4계층 사전 안전 게이트 & 무중단 Fallback 엔진
│   └── genre-classification-pipeline.md   # 도서 16개 표준 장르 분류 및 30일 캐싱
├── observability/                         # 관측 스택 & 모니터링
│   ├── cloudwatch-dashboard-guide.md      # AWS CloudWatch 커스텀 대시보드 운영 가이드
│   ├── cloudwatch-dashboard-stack.yaml    # 대시보드 선언형 배포 CloudFormation IaC
│   ├── dashboard.json                     # 대시보드 원본 위젯 JSON
│   └── prometheus-grafana-loki-guide.md   # Prometheus/Tempo/Loki 관측 스택 운영 가이드
├── cicd/                                  # CI/CD 파이프라인
│   └── github-actions-argocd-guide.md     # GitHub Actions & ArgoCD GitOps 배포 가이드
└── security/                              # AI 보안 & 거버넌스
    ├── bedrock-guardrail-guide.md         # Amazon Bedrock Guardrails 보안 게이트 운영 가이드
    └── guardrail-stack.yaml               # 가드레일 & IRSA 권한 선언형 CloudFormation IaC
```

---

## 🚀 빠른 링크 및 가이드 요약

### 1. API Wire 계약 & ADR
- [OpenAPI 3.0 스펙 문서](api/openapi.yaml): `/api/v1/chat`, `/api/v1/classify-genre`
- [API 아키텍처 결정 기록 (ADR)](api/decisions/README.md):
  - [ADR 0002](api/decisions/0002-book-genre-classification.md): 16개 표준 장르 분류 API
  - [ADR 0003](api/decisions/0003-librarian-agent-integration.md): 사서 에이전트 연동 및 시그널 조율
  - [ADR 0004](api/decisions/0004-my-library-integration.md): 내 서재 CRUD API 연동
  - [ADR 0005](api/decisions/0005-library-books-card-response.md): 서재 도서 구조화 카드 응답
  - [ADR 0006](api/decisions/0006-streaming-library-books-markdown-format.md): 스트리밍 서재 도서 포맷
  - [ADR 0007](api/decisions/0007-chat-authentication-ownership.md): 채팅 인증 토큰 소유권 및 401 격리
  - [ADR 0008](api/decisions/0008-recommended-book-card-structuring.md): 추천 도서 카드 구조화

### 2. 핵심 기능 상세 명세 (Features)
- [알라딘 서지 실조회 & 검증 파이프라인](features/aladin-book-verification.md):
  - 제목·저자 전처리 정규화 ➔ `by-title-author`(ISBN) ➔ `search?isbn=`(실제 총 쪽수) 2단 조회
  - Redis 30일(2,592,000초) 캐시 및 `asyncio.gather` 병렬화
- [다계층 안전 게이트 & 무중단 Fallback 엔진](features/multi-tier-safety-and-fallback.md):
  - Gate 1(Safety 109 핫라인) ➔ Gate 2(Input 자모 필터) ➔ Gate 3(Bedrock Guardrails)
  - 원격 사서 장애 시 인프로세스 페르소나 및 switch_to 스위칭 자체 완결 엔진
- [16개 표준 장르 분류 파이프라인](features/genre-classification-pipeline.md):
  - ISBN 단일 식별자 기반 제로샷 분류, 3단계 완화 매칭 테이블 및 `NONE` 방어선

### 3. AWS 서비스 & 선언형 IaC (Infrastructure as Code)
모든 AWS 자원은 재현성과 환경 격리를 위해 선언형 CloudFormation 템플릿으로 제공됩니다:
- **보안 (Amazon Bedrock Guardrails)**:
  - 템플릿: [`guardrail-stack.yaml`](security/guardrail-stack.yaml)
  - 가이드: [Bedrock Guardrails 가이드](security/bedrock-guardrail-guide.md)
  - 내용: 프롬프트 공격/탈옥/PII 방어 Guardrail, 버전 1, 파드 IRSA IAM Role 권한
- **관측성 (AWS CloudWatch LLM 커스텀 대시보드)**:
  - 템플릿: [`cloudwatch-dashboard-stack.yaml`](observability/cloudwatch-dashboard-stack.yaml)
  - 가이드: [CloudWatch 대시보드 가이드](observability/cloudwatch-dashboard-guide.md)
  - 내용: E2E 레이턴시/TTFT, 실시간 Bedrock USD 비용, 프롬프트 캐시 절감률, Tavily 검색 캐시 히트율

### 4. 관측 스택 (Prometheus / Tempo / Loki)
- [Prometheus/Grafana(Tempo)/Loki 운영 가이드](observability/prometheus-grafana-loki-guide.md):
  - `http_server_requests_seconds` Micrometer 호환 히스토그램, `ServiceMonitor` 스크레이핑 등록
  - OTel 자동 계측(FastAPI/Redis/Botocore/HTTPX) 및 `_SanitizingSpanExporter` 민감정보 스크러빙
  - stdout JSON 로깅 → Grafana Alloy → Loki, `trace_id`/`span_id` 기반 Tempo Correlation

### 5. CI/CD 파이프라인 (GitHub Actions & ArgoCD)
- [GitHub Actions & ArgoCD GitOps 배포 가이드](cicd/github-actions-argocd-guide.md):
  - `pr-convention-check.yml`: PR 제목/본문 컨벤션 검증
  - `build-push-ecr.yml`: ECR 이미지 빌드·푸시 및 Kustomize `newTag` 자동 갱신(GitOps 커밋)
  - ArgoCD `Application`(`argocd/application-dev.yaml`/`prod.yaml`) 기반 EKS 자동 sync
