# backend-discovery

DPYB(Don't Paw Get Your Book)의 **AI · 탐색(Discovery) 전담 마이크로서비스**입니다.

Strands Agents SDK와 AWS Bedrock(Claude Haiku 4.5)을 기반으로, 실시간 웹 검색(Tavily)과 내부 마이크로서비스 API 연동을 통해 **도서 추천 · 내 서재 검색 · 사서 상담**을 하나의 대화창에서 원스톱으로 처리하는 AI 오케스트레이션 및 표준 장르 분류 서비스를 제공합니다.

---

## 🏛️ 시스템 아키텍처 & 에이전트 토폴로지

### 1. 시스템 통합 아키텍처 (마이크로서비스 & 인프라 뷰)
디스커버리 오케스트레이터와 사서 에이전트(`backend-librarian`), 도서 CRUD(`backend-book`) 및 외부 API 간의 마이크로서비스 연동 구조입니다.

```mermaid
flowchart TB
    Client["📱 클라이언트 (my-reading-room)"]

    %% 1. backend-discovery (오케스트레이터 & 추천 & 분류)
    subgraph DiscoveryRepo["📦 backend-discovery (AI 오케스트레이션 서비스)"]
        direction TB
        Router["FastAPI Router<br/>POST /api/v1/chat"]

        subgraph Guardrails["다계층 보안 & 가드레일 레이어"]
            direction LR
            G_Safety["Safety Gate (109 핫라인)"]
            G_Input["Input Gate (자모 단락)"]
            G_Bedrock["Bedrock Guardrails (프롬프트/PII 방어)"]
            G_Safety --> G_Input --> G_Bedrock
        end

        Orchestrator["🧠 오케스트레이터 에이전트 (Strands Agents SDK)<br/>LLM: AWS Bedrock Claude Haiku 4.5<br/>복합 의도 분류 & 도구 위임/체이닝"]

        Redis[("⚡ Redis (ChatSessionStore)<br/>20턴 대화 히스토리 + 세션 메타")]

        subgraph LocalAgent["로컬 서브 에이전트 (In-Process)"]
            Recommend["🔍 도서 추천 에이전트 (recommend_books)<br/>웹 검색 ➔ 알라딘 검증 ➔ truncate"]
        end

        LocalFallback["사서 로컬 Fallback 판단기<br/>(원격 사서 장애 시 무중단 페르소나 대체)"]

        Router --> Guardrails --> Orchestrator
        Orchestrator <--> Redis
        Orchestrator --> Recommend
    end

    %% 2. backend-librarian (사서 페르소나 서비스)
    subgraph LibrarianRepo["🪿 backend-librarian (사서 페르소나 서비스)"]
        direction TB
        L_API["FastAPI Entrypoint<br/>POST /api/v1/chat"]

        subgraph Librarians["사서 페르소나 에이전트군"]
            Cat["🐱 블루 (고양이 사서)<br/>특화: 추리 / 미스터리"]
            Stork["🪿 슈빌 (황새 사서)<br/>특화: 비즈니스 / 경제"]
        end

        subgraph EnvTools["환경 & 시그널 모듈"]
            Weather["Open-Meteo 날씨 API"]
            Mood["Time & Mood Mapper"]
            SafetyNet["Switch Safety Net"]
        end

        L_API --> SafetyNet --> Librarians
        L_API --> Weather --> Mood
    end

    %% 3. backend-book (도서 CRUD 서비스)
    subgraph BookRepo["📚 backend-book (도서 CRUD 서비스)"]
        direction TB
        BookService["내 서재 도서 조회 & 알라딘 검색 대행<br/>GET /api/v1/library/books<br/>GET /api/v1/books/search"]
    end

    %% 외부 연동
    Tavily[["🌐 Tavily Web Search API"]]
    Aladin[["📖 알라딘 Open API"]]
    Bedrock[["☁️ AWS Bedrock (Haiku 4.5)"]]

    %% 클라이언트 호출
    Client ==>|"1. 대화 요청 (JWT, 좌표, stream)"| Router

    %% 디스커버리 ➔ 사서 연동
    Orchestrator ==>|"도구 1: consult_librarian (HTTP)"| L_API
    Librarians -.->|"사서 첫마디 + 날씨 시그널 + switch_to"| Orchestrator
    L_API -.->|"타임아웃/에러 시"| LocalFallback
    LocalFallback -.-> Orchestrator

    %% 디스커버리 ➔ 서재 조회
    Orchestrator ==>|"도구 3: search_my_library (Bearer 패스스루)"| BookService

    %% 추천 에이전트 ➔ 외부 검색 및 서지 검증
    Recommend ==>|"후보 도서 실시간 탐색"| Tavily
    Recommend ==>|"페이지수 실조회"| BookService
    BookService ==>|"서지 조회"| Aladin

    %% LLM 백엔드 & 가드레일
    G_Bedrock -.->|"ApplyGuardrail"| Bedrock
    Orchestrator -.-> Bedrock
    Recommend -.-> Bedrock
    Librarians -.-> Bedrock

    %% 스타일링 (명확한 고대비 다크 텍스트 & 경계선)
    style DiscoveryRepo fill:#eff6ff,stroke:#2563eb,stroke-width:3px,color:#0f172a
    style LibrarianRepo fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#0f172a
    style BookRepo fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#0f172a
    style Guardrails fill:#fee2e2,stroke:#ef4444,stroke-dasharray: 2 2,color:#7f1d1d
    style G_Bedrock fill:#ffffff,stroke:#ef4444,color:#7f1d1d
    style LocalAgent fill:#dbeafe,stroke:#3b82f6,color:#1e3a5f
    style Redis fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#581c87
    style Orchestrator fill:#bfdbfe,stroke:#1d4ed8,stroke-width:2px,color:#0f172a
    style LocalFallback fill:#fee2e2,stroke:#ef4444,color:#7f1d1d
    style Client fill:#ffffff,stroke:#334155,stroke-width:2px,color:#0f172a
    style Tavily fill:#ffffff,stroke:#16a34a,stroke-width:2px,color:#14532d
    style Aladin fill:#ffffff,stroke:#dc2626,stroke-width:2px,color:#7f1d1d
    style Bedrock fill:#ffffff,stroke:#d13b68,stroke-width:2px,color:#831843
```

---

### 2. 순수 에이전트 토폴로지 (Agent-as-a-Tool 뷰)
인프라 세부사항을 배제하고, **오케스트레이터와 서브 에이전트 간의 계층적 역할 분담 및 도구 조율 흐름**을 나타낸 다이어그램입니다.

```mermaid
flowchart TD
    UserPrompt(["💬 사용자 자연어 입력<br/>(예: '비도 오는데 울적해, 내 서재 책이랑 어울리는 추리소설 2권 추천해줘')"])

    %% 최상위 지휘자
    subgraph L0["Level 0: 최상위 의도 판단 & 조율 (backend-discovery)"]
        Orchestrator["🧠 오케스트레이터 에이전트 (Orchestrator Agent)<br/>역할: 사용자 의도 분석, 상황 판단, 하위 에이전트/도구 조율 & 최종 응답 합성<br/>동적 페르소나: 현재 활성 사서(블루🐱 / 슈빌🪿)의 톤앤매너 장착"]
    end

    %% 하위 협력 에이전트 및 도구 (Agent-as-a-Tool)
    subgraph L1["Level 1: 전문 서브 에이전트 & 도구 (Agent-as-a-Tool)"]
        direction LR

        subgraph LibrarianGroup["사서 페르소나 에이전트 (backend-librarian)"]
            direction TB
            LibrarianTool["🪿 consult_librarian (사서 상담 도구)"]
            CatAgent["🐱 블루 (고양이 사서)<br/>감성/공감 & 추리/미스터리 특화"]
            StorkAgent["🪿 슈빌 (황새 사서)<br/>전문성 & 비즈니스/커리어 특화"]
            LibrarianTool --> CatAgent
            LibrarianTool --> StorkAgent
        end

        subgraph SearchGroup["도서 탐색 & 추천 에이전트 (In-Process)"]
            direction TB
            RecommendTool["🔍 recommend_books (도서 추천 도구)"]
            TavilySearch["웹 실시간 검색<br/>(실존 도서 후보 탐색)"]
            AladinVerify["서지/쪽수 2단 검증<br/>(환각 방지)"]
            RecommendTool --> TavilySearch --> AladinVerify
        end

        subgraph LibraryGroup["내 서재 분석 도구 (backend-book)"]
            direction TB
            LibraryTool["📚 search_my_library (내 서재 검색)"]
            StatusFilter["독서 상태 & 장르 필터링<br/>(읽은 책 / 읽는 중인 책)"]
            LibraryTool --> StatusFilter
        end
    end

    %% 상호작용 및 조율 흐름
    UserPrompt ==> Orchestrator

    Orchestrator ==>|"1. 무드/상황 해석 & 사서 대화 위임"| LibrarianTool
    LibrarianGroup -.->|"사서 첫마디 + 날씨/무드 시그널 + 사서 전환(switch_to)"| Orchestrator

    Orchestrator ==>|"2. 개인화 문맥 확인 (내 서재 조회)"| LibraryTool
    LibraryGroup -.->|"사용자 서재 도서 목록 & 독서 취향"| Orchestrator

    Orchestrator ==>|"3. 분석된 무드 + 서재 문맥 기반 정밀 도서 탐색 위임"| RecommendTool
    SearchGroup -.->|"검증된 도서 추천 카드 (제목, 저자, 쪽수, 추천이유)"| Orchestrator

    %% 최종 응답
    FinalResponse(["✨ 최종 사용자 응답<br/>(사서의 공감 멘트 + 내 서재 언급 + 검증된 추천 도서 카드)"])
    Orchestrator ==> FinalResponse

    %% 스타일링 (시인성 확보: 명확한 다크 텍스트 & 경계선)
    style L0 fill:#e8f4fd,stroke:#1a73e8,stroke-width:2px,color:#1e293b
    style L1 fill:#f8f9fa,stroke:#475569,stroke-dasharray: 3 3,color:#1e293b
    style Orchestrator fill:#bfdbfe,color:#0f172a,stroke:#2563eb,stroke-width:2px
    style LibrarianGroup fill:#fef3c7,stroke:#d97706,stroke-width:2px,color:#1e293b
    style SearchGroup fill:#dcfce7,stroke:#16a34a,stroke-width:2px,color:#1e293b
    style LibraryGroup fill:#f3e8ff,stroke:#9333ea,stroke-width:2px,color:#1e293b
    style CatAgent fill:#ffffff,stroke:#d97706,color:#0f172a
    style StorkAgent fill:#ffffff,stroke:#d97706,color:#0f172a
    style TavilySearch fill:#ffffff,stroke:#16a34a,color:#0f172a
    style AladinVerify fill:#ffffff,stroke:#16a34a,color:#0f172a
    style StatusFilter fill:#ffffff,stroke:#9333ea,color:#0f172a
```

---

### 3. backend-discovery 내부 상세 파이프라인 (Agent-as-a-Tool 실행 엔진)
오케스트레이터가 **사용자 입력을 분석하여 3개의 Agent-as-a-Tool을 어떻게 호출·합성하는지** 나타낸 상세 실행 파이프라인입니다.

```mermaid
flowchart TD
    %% ==========================================
    %% 📦 backend-discovery 내부 파이프라인
    %% ==========================================
    subgraph DiscoveryPipeline["📦 backend-discovery 내부 오케스트레이션 파이프라인"]
        direction TB

        %% 1. 진입 및 가드레일
        Entry["FastAPI Entrypoint (/api/v1/chat)"]
        
        subgraph GatePipeline["🛡️ 4단계 다계층 보안 & 가드레일 레이어"]
            direction TB
            G0["0차: Bearer 토큰 Presence Check (401 즉시 차단)"]
            G1["1차: Safety Gate (자해/위기 109 핫라인 즉시 단락)"]
            G2["2차: Input Gate (자모/단발/이모지 결정론적 우회)"]
            G3["3차: Bedrock Guardrails Gate (프롬프트 인젝션/탈옥/PII 사전 차단)"]
            G0 --> G1 --> G2 --> G3
        end

        %% 2. 오케스트레이터 에이전트 코어
        subgraph OrchestratorCore["🧠 Orchestrator Agent Core (Bedrock Haiku 4.5)"]
            direction TB
            SessionStore[("Redis ChatSessionStore<br/>20턴 슬라이딩 윈도우 + 세션 메타")]
            PromptInjector["동적 페르소나 주입<br/>(CAT_PROMPT 🐱 / STORK_PROMPT 🪿)"]
            ReasoningLoop["Strands Agent ReAct 추론 루프<br/>(의도 분석 & 도구 호출 계획 수립)"]
            SessionStore --> ReasoningLoop
            PromptInjector --> ReasoningLoop
        end

        %% 3. Agent-as-a-Tool 분과
        subgraph AgentTools["🛠️ Agent-as-a-Tool 실행 레이어"]
            direction LR

            subgraph RemoteLibrarianTool["HTTP Agent Tool: consult_librarian"]
                direction TB
                T_Lib["backend-librarian 호출"]
                FallbackCheck{"응답 유효성 검사<br/>(20초 타임아웃 / 5xx 감지)"}
                LocalEngine["Discovery 자체 완결 로컬 엔진<br/>(evaluate_local_persona_response)"]
                T_Lib --> FallbackCheck
                FallbackCheck -.->|장애 시| LocalEngine
            end

            subgraph LocalResearchAgent["In-Process Agent Tool: recommend_books"]
                direction TB
                T_Rec["도서 리서치 에이전트 인보크"]
                TavilyCall["1. Tavily 웹 실시간 도서 검색"]
                AladinFactCheck["2. 알라딘 서지/쪽수 2단 실조회"]
                TruncateFilter["3. count 상한 강제 (truncate_books)"]
                T_Rec --> TavilyCall --> AladinFactCheck --> TruncateFilter
            end

            subgraph RemoteLibraryTool["HTTP Data Tool: search_my_library"]
                direction TB
                T_My["backend-book 서재 API 호출"]
                AuthPass["Bearer JWT 패스스루 (IDOR 원천 방지)"]
                FormatLLM["독서 상태 & 장르별 LLM 프롬프트 변환"]
                T_My --> AuthPass --> FormatLLM
            end
        end

        %% 4. 합성 및 응답
        subgraph OutputPipeline["최종 응답 합성 & 스트리밍"]
            direction TB
            ResponseComposer["사서 첫마디 + 도서 카드 마크다운 합성"]
            FastStream["Fast TTFB 스트리밍 / 동기 응답 전송"]
            ObsLog["Observability (OTel / Prometheus / CloudWatch)"]
            ResponseComposer --> FastStream --> ObsLog
        end

        %% 전체 연결 흐름
        Entry --> GatePipeline
        G3 -->|통과| ReasoningLoop
        ReasoningLoop ==>|"의도: 페르소나/날씨"| RemoteLibrarianTool
        ReasoningLoop ==>|"의도: 실시간 도서 탐색"| LocalResearchAgent
        ReasoningLoop ==>|"의도: 서재 조회/필터링"| RemoteLibraryTool

        RemoteLibrarianTool ==> ResponseComposer
        LocalResearchAgent ==> ResponseComposer
        RemoteLibraryTool ==> ResponseComposer
    end

    %% 스타일링 (명확한 텍스트 컬러 주입)
    style DiscoveryPipeline fill:#f8fafc,stroke:#334155,stroke-width:2px,color:#0f172a
    style GatePipeline fill:#fee2e2,stroke:#ef4444,stroke-dasharray: 3 3,color:#7f1d1d
    style OrchestratorCore fill:#eff6ff,stroke:#2563eb,stroke-width:2px,color:#1e3a5f
    style AgentTools fill:#f1f5f9,stroke:#475569,stroke-dasharray: 2 2,color:#0f172a
    style RemoteLibrarianTool fill:#fef3c7,stroke:#d97706,color:#78350f
    style LocalResearchAgent fill:#dcfce7,stroke:#16a34a,color:#14532d
    style RemoteLibraryTool fill:#f3e8ff,stroke:#9333ea,color:#581c87
    style OutputPipeline fill:#fef9c3,stroke:#ca8a04,stroke-width:2px,color:#713f12
```

---

## 🛠️ 기술 스택

| 영역 | 기술 | 설명 |
| :--- | :--- | :--- |
| **언어 / 런타임** | Python 3.12, FastAPI (async) | 비동기 고성능 REST API 및 스트리밍 처리 |
| **패키지 관리** | uv (`pyproject.toml`, `uv.lock`) | 초고속 결정론적 의존성 격리 |
| **AI / 에이전트** | Strands Agents SDK | Agent-as-a-Tool 패턴 기반 오케스트레이션 |
| **LLM 추론** | AWS Bedrock (Claude Haiku 4.5) | 글로벌 프로필 (`global.anthropic.claude-haiku-4-5-20251001-v1:0`, `us-east-1`) |
| **외부 검색** | Tavily Web Search API | `search_depth="basic"`, `sanitize_search_results` 페이로드 축소 |
| **서지 검증** | 알라딘 Open API (via backend-book) | 제목·저자 기반 ISBN/총 페이지수 2단 실조회 (환각 방지) |
| **캐시 & 세션** | Redis 7 (`ChatSessionStore`) | 대화 20턴 슬라이딩 윈도우, 세션 메타(좌표/사서ID), 서지 캐시(30일) |
| **보안 & 안전** | AWS Bedrock Guardrails, 109 Safety Gate | 악의적 프롬프트/탈옥/PII 사전 차단, 위기/자해 109 핫라인 즉시 우회 |
| **관측성** | OpenTelemetry + Prometheus + CloudWatch | OTel 트레이싱(Tempo), JSON 로그(Loki), `/metrics`, Bedrock 비용/지연 메트릭 |

---

## 📂 저장소 구조

```text
backend-discovery/
├── src/discovery/
│   ├── main.py                  # FastAPI 앱 팩토리, Lifespan, OTel/미들웨어 등록
│   ├── core/                    # 설정(config), JSON 로깅, 트레이싱(OTel), 메트릭, CloudWatch
│   ├── domain/
│   │   ├── orchestrator/        # 오케스트레이터 에이전트 빌더, 사서별 전용 프롬프트, 도구군
│   │   │   ├── tools/           # recommend_tool, librarian_tool, library_tool
│   │   │   ├── gates/           # safety_gate(109 핫라인), input_gate(자모 단락)
│   │   │   ├── bedrock_guardrail_gate.py  # Amazon Bedrock Guardrails 입력 검증 게이트
│   │   │   └── fallback.py      # 사서 장애 대응 로컬 페르소나 fallback 엔진
│   │   ├── librarian/           # 도서 추천 로컬 에이전트, 후처리기(truncate, sanitize)
│   │   └── genre/               # 도서 16개 표준 장르 분류 프롬프트 및 파서
│   ├── application/             # orchestrator_service, genre_classifier_service
│   ├── infrastructure/
│   │   ├── cache/               # Redis 클라이언트, ChatSessionStore
│   │   └── search/              # Tavily 검색 도구, 캐시, 요청 리미터
│   └── api/
│       ├── deps.py              # 의존성 주입 배선 (DI)
│       ├── schemas/             # ChatRequest/Response, GenreRequest/Response
│       └── v1/routers/          # chat.py, genre.py
├── docs/api/                    # openapi.yaml, ADR 결정 문서
├── k8s/                         # Kubernetes 배포 매니페스트 (base, overlays/dev)
└── tests/                       # 단위 테스트(305건 100% 통과) 및 Redis 통합 테스트
```

---

## 🚀 API 계약 (API Contract)

### 1. POST /api/v1/chat (별칭: /chat)
오케스트레이터와 대화하며, 의도에 따라 도서 추천, 사서 상담, 내 서재 조회를 복합 수행합니다.

**요청 헤더:**
- `Authorization: Bearer <token>` (필수, 사용자 인증 및 서재 연동용)

**요청 바디 (ChatRequest):**
```json
{
  "message": "비도 오는데 울적해, 내 서재 책이랑 어울리는 추리소설 2권 추천해줘",
  "session_id": "optional-uuid",
  "stream": false,
  "latitude": 37.5145,
  "longitude": 127.1058
}
```

**응답 바디 (ChatResponse, stream=false):**
```json
{
  "message": "비 오는 날엔 차분하게 몰입할 수 있는 추리소설이 최고다냥! 서재에 있는 책들을 참고해서 딱 맞는 책으로 선별했다냥 🐾\n\n### 📖 백야행\n- **저자**: 히가시노 게이고 (592쪽)\n- **장르**: LITERARY_FICTION\n- **추천 이유**: 서재에 등록된 도서들과 어우러져 깊은 여운을 주는 대표 명작 추리소설입니다.",
  "session_id": "sess-uuid",
  "switch_to": null,
  "signals": {
    "weather": {"weather": "비", "temperature": 21.0, "is_rainy": true},
    "mood": "gloomy",
    "genre_focus": ["미스터리", "스릴러"]
  },
  "library_books": [],
  "recommended_books": [
    {
      "title": "백야행",
      "author": "히가시노 게이고",
      "total_pages": 592,
      "genre": "LITERARY_FICTION",
      "recommendation_reason": "서재에 등록된 도서들과 어우러져 깊은 여운을 주는 대표 명작 추리소설입니다."
    }
  ]
}
```

*스트리밍(`stream=true`) 시 본문은 SSE 청크로 전달되며 `X-Session-Id`, `X-Signals`, `X-Switch-To`, `X-Library-Books` 헤더가 함께 노출됩니다.*

### 2. POST /api/v1/classify-genre
도서의 ISBN을 분석하여 DPYB ERD 규격 16개 표준 장르 중 1개로 자동 분류합니다.

---

## ⚙️ 주요 환경 변수

| 변수명 | 설명 | 기본값 |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | LLM 구동 엔진 (`bedrock` 또는 `mock`) | `mock` |
| `ORCHESTRATOR_MODEL_ID` | 오케스트레이터 모델 ID (Haiku 4.5) | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `LIBRARIAN_MODEL_ID` | 추천 에이전트 모델 ID | `global.anthropic.claude-haiku-4-5-20251001-v1:0` |
| `LIBRARIAN_AGENT_URL` | 사서 마이크로서비스 URL | `http://localhost:8000` (dev: K8s Service DNS) |
| `LIBRARY_API_URL` | 내 서재 API (backend-book) URL | 클러스터 도메인 |
| `REDIS_HOST` / `PORT` | 세션/캐시 저장소 Redis 접속 정보 | `localhost:6379` |
| `TAVILY_API_KEY` | 실시간 웹 도서 검색 API 키 | - |
| `ENABLE_PROMPT_CACHING` | Bedrock 프롬프트 캐싱 활성화 여부 | `true` |
| `ENABLE_CLOUDWATCH_METRICS`| AWS CloudWatch LLM 커스텀 메트릭 발행 | `false` (dev: `true`) |

---

## 💻 로컬 개발 환경 실행

```bash
# 1. 의존성 동기화
uv sync

# 2. Redis 기동
docker compose up -d redis

# 3. 환경 변수 설정 (.env)
cp .env.example .env

# 4. 서버 기동 (포트 8001)
uv run uvicorn src.discovery.main:app --host 0.0.0.0 --port 8001 --reload

# 5. 검증 (정적 분석 & 단위 테스트)
uv run ruff check .
uv run mypy .
uv run pytest -m "not integration"
```


