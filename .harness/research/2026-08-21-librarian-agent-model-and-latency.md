# 사서 에이전트 — 모델 선택 및 속도 최적화 기법

- 조사일: 2026-08-21
- 관련 티켓: 없음 (사서 에이전트 새 레포 구현 시 참고 자료)
- 상태: 조사 완료. 실제 구현(새 레포)에서 실측 후 확정할 것.

## 배경

`2026-08-21-strands-agents-poc-design.md`에서 다룬 "사서 에이전트를 Strands
Agents SDK로 구현"이 실제로 착수되면서, 웹 검색 도구를 쓰는 이 에이전트에
어떤 Bedrock 모델을 쓸지와 응답 속도를 어떻게 최적화할지를 조사했다. 이
에이전트는 backend-discovery가 아니라 별도의 사서 에이전트 레포에서 구현되지만,
그 레포 착수 시 바로 참고할 수 있도록 이 저장소의 `.harness/research/`에
남겨둔다.

## 1. 모델 선택

웹 검색 도구를 호출해 도구 결과를 파싱하고 자연스러운 한국어 추천 문장을
생성하는 워크로드다. 최상위 추론 모델이 필요한 작업이 아니라 **빠르고 저렴한
모델**이 적합하다.

### 1차 추천 — Claude Haiku 4.5 (`bedrock-runtime`, Converse API)

- "agent 성능"에 최적화된 경량 모델로 AWS가 공식 소개하며, "real-time customer
  service, latency-sensitive use cases"를 명시적 권장 사용처로 든다. [출처: AWS
  CDK BedrockFoundationModel 문서](https://docs.aws.amazon.com/cdk/api/v2/docs/@aws-cdk_aws-bedrock-alpha.BedrockFoundationModel.html)
- 컨텍스트 200K / 최대 출력 64K로 웹 검색 결과(긴 텍스트)를 컨텍스트에 담기에
  충분하다. [출처: AWS Bedrock 모델 카드](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html)
- 도구 사용(tool use)이 검증된 모델 계열이라 Strands `@tool` 기반 웹 검색
  도구 호출과 궁합이 좋다.

### 대안 — Amazon Nova Lite

- Popsa의 실측 A/B 비교: Claude 3 Haiku 대비 응답 시간이 훨씬 빠르고(500 토큰
  출력 기준 6.8초 vs 2.4초) 비용도 낮으면서 품질은 거의 동등했다. [출처: AWS
  ML 블로그 — Popsa Nova 사례](https://aws.amazon.com/blogs/machine-learning/how-popsa-used-amazon-nova-to-inspire-customers-with-personalised-title-suggestions/)
- **주의**: 이 비교는 Claude **3** Haiku(구형) 기준이라 최신 **Haiku 4.5**와
  직접 비교한 자료는 아직 없다. 실제 구현 시 두 모델을 A/B로 실측 비교할 것.

### 결론 및 실행 순서

1. Claude Haiku 4.5로 시작해 tool use 정확도(웹 검색 도구를 올바르게 호출하고
   결과를 정확히 반영하는지)를 먼저 확보한다.
2. 비용/속도가 더 중요해지면 Nova Lite로 A/B 테스트한다. Bedrock의 단일 API
   덕에 모델 ID만 바꿔서 전환 가능하다. [출처: AWS ML 블로그 — Bedrock 비용
   최적화](https://aws.amazon.com/blogs/machine-learning/effective-cost-optimization-strategies-for-amazon-bedrock/)
3. 정량 비교 기준(응답 시간, 추천 품질에 대한 사용자 피드백, 비용)을 미리
   정해두고 A/B를 진행할 것 — Popsa 사례도 이 세 축으로 비교했다.

## 2. 속도 최적화 기법 (구현 우선순위 순)

### (1) 스트리밍 응답 — 체감 효과가 가장 큼

- Strands는 `stream_async`로 텍스트·도구 사용·추론 단계를 실시간 스트리밍하는
  것을 1급으로 지원하며, FastAPI `StreamingResponse`와 바로 연결하는 예제가
  공식 문서에 있다. [출처: Strands 블로그 — 1.0 발표](https://strandsagents.com/blog/strands-agents-1-0/index.md)
- 프론트 연결 테스트가 목표라면, 전체 응답 완성을 기다리지 않고 첫 토큰이
  나오는 시간(TTFT)만 줄여도 "느리다"는 체감이 크게 준다. 처음부터 토큰
  단위 스트리밍 구조로 설계할 것.

```python
# Strands 공식 예제 패턴 (참고용, 실제 사서 에이전트 구현 시 조정)
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from strands import Agent

app = FastAPI()

@app.post("/chat")
async def chat_endpoint(message: str):
    async def stream_response():
        async for event in librarian_agent.stream_async(message):
            yield event  # 텍스트/도구 사용/추론 이벤트를 그대로 흘려보낸다
    return StreamingResponse(stream_response())
```

### (2) Bedrock 지연시간 최적화 추론 (Latency-Optimized Inference)

- API 호출 시 `performanceConfig.latency = "optimized"`만 지정하면 별도
  설정/파인튜닝 없이 응답 속도가 빨라진다.
- 지원 모델: Claude 3.5 Haiku, Nova Pro, Llama 3.1 70B/405B. **주의**: 이 조사
  시점 기준 프리뷰 기능이며 리전이 US East(Ohio)/US West(Oregon)로 한정된다.
  **Haiku 4.5가 이 리스트에 포함되는지는 구현 시점에 AWS 문서로 재확인해야
  한다** (조사 시점 자료에는 3.5 Haiku만 명시됨). [출처: AWS Bedrock 공식
  문서 — Latency Optimized Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/latency-optimized-inference.html)

```python
performanceConfig = {"latency": "optimized"}  # Converse API 호출 시 전달
```

### (3) 프롬프트 캐싱 (Prompt Caching)

- 사서 페르소나의 system prompt, few-shot 예시, 도구 정의처럼 매 요청마다
  반복되는 고정 부분을 캐싱하면 그 부분의 재계산을 건너뛰어 지연시간과 입력
  토큰 비용이 함께 줄어든다. "문서를 매번 다시 처리하지 않아도 되는" 워크로드에
  특히 효과적이라고 AWS가 명시한다. [출처: AWS Bedrock 공식 문서 — Prompt
  Caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
- 사서 에이전트의 `system_prompt` + 도구 스펙(웹 검색 도구 정의)은 거의
  고정이므로 캐싱 적용 여지가 크다. Strands가 캐싱 지점을 얼마나 자동화해
  주는지는 구현 시점에 Strands 모델 프로바이더 문서를 재확인할 것(이 조사에서
  Strands 쪽 캐싱 API까지는 확인하지 못함).

### (4) 웹 검색 자체의 지연시간 관리 (검색 결과 캐싱)

- Strands의 `http_request` 도구로 웹 검색을 호출하면, 외부 API 왕복 지연이
  전체 응답 시간의 큰 부분을 차지할 수 있다.
- 동일 질문/검색어가 반복되는 경우(예: "오늘 추천 도서") 검색 결과를 짧은
  TTL로 캐싱하는 semantic caching 패턴을 검토한다. backend-discovery가 이미
  `ChatSessionStore`로 Redis를 운영 중이므로(`.harness/DECISIONS.md` 2026-08-21
  방향 전환 참고), 사서 에이전트 레포도 자체 Redis(또는 ElastiCache)를 검색
  캐시 용도로 두는 걸 고려할 수 있다 — **단, 이건 대화 세션 데이터가 아니라
  검색 캐시이므로 backend-discovery의 `ChatSessionStore`와는 별개 저장소로
  설계해야 한다**(세션 스토어 소유권 관련 논의와 혼동하지 않을 것).

### (5) Native Async + 병렬 도구 실행

- Strands 1.0부터 도구와 모델 프로바이더가 논블로킹 async로 동작해, 여러
  도구를 동시에 호출해야 하는 경우(예: 여러 검색어로 병렬 웹 검색) 순차
  실행보다 빨라진다. [출처: Strands 블로그 — 1.0 발표](https://strandsagents.com/blog/strands-agents-1-0/index.md)

### 적용 우선순위 (구현 비용 대비 효과)

1. 스트리밍 응답 — 구현 비용 낮음, 체감 효과 큼. 처음부터 이 구조로 설계할 것.
2. 프롬프트 캐싱 — 구현 비용 낮음(설정 위주), system prompt/도구 정의가
   고정이라 즉시 효과.
3. Bedrock 지연시간 최적화 추론 — 리전/모델 가용성을 구현 시점에 재확인 후 적용.
4. 웹 검색 결과 캐싱 — 트래픽이 늘고 반복 질문 패턴이 보이면 추가.
5. 병렬 도구 실행 — 여러 검색어를 동시에 던지는 설계가 실제로 필요해지면 적용.

## 참고 자료

- [AWS CDK — BedrockFoundationModel (Claude Haiku 4.5)](https://docs.aws.amazon.com/cdk/api/v2/docs/@aws-cdk_aws-bedrock-alpha.BedrockFoundationModel.html)
- [AWS Bedrock — Claude Haiku 4.5 모델 카드](https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-anthropic-claude-haiku-4-5.html)
- [AWS ML 블로그 — Popsa의 Nova 모델 비교 사례](https://aws.amazon.com/blogs/machine-learning/how-popsa-used-amazon-nova-to-inspire-customers-with-personalised-title-suggestions/)
- [AWS ML 블로그 — Bedrock 비용 최적화 전략](https://aws.amazon.com/blogs/machine-learning/effective-cost-optimization-strategies-for-amazon-bedrock/)
- [AWS Bedrock 공식 문서 — Latency Optimized Inference](https://docs.aws.amazon.com/bedrock/latest/userguide/latency-optimized-inference.html)
- [AWS Bedrock 공식 문서 — Prompt Caching](https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html)
- [Strands 블로그 — Strands Agents 1.0 (Native Async, 스트리밍)](https://strandsagents.com/blog/strands-agents-1-0/index.md)
- [Strands 공식 문서 — Streaming Responses](https://strandsagents.com/docs/user-guide/concepts/streaming/index.md)
- [Strands 공식 예제 — weather_forecaster (http_request 도구 패턴)](https://strandsagents.com/docs/examples/python/weather_forecaster/index.md)

이 문서는 조사 결과 보관용이다. 실제 구현 시 실측(응답 시간, 비용, 추천 품질)
결과를 바탕으로 모델/기법 선택을 확정하고, 확정된 내용은 사서 에이전트 레포의
자체 결정 문서(그 레포가 `.harness`를 쓴다면 `DECISIONS.md`, 아니라면 해당
레포의 컨벤션에 따름)에 기록한다.
