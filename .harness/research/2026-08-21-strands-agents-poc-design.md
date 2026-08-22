# Strands Agents SDK 도입 설계 (PoC 수준) — backend-discovery

- 조사일: 2026-08-21
- 관련 티켓: 없음 (CLIAR-51과 무관한 별도 조사 요청, 코드 작성 없이 설계 초안만)
- 상태: 설계 제안, 결정 대기 (팀 논의 후 사용자가 결정)

## 목표 (요청 원문 기준)

- "추천 에이전트"는 서비스 전체에 공용으로 하나.
- "사서 페르소나"는 에이전트별로 분리 가능한 구조 (지금은 사서 하나뿐이지만, 이후
  다른 페르소나가 추가될 수 있는 구조).
- 나중에 날씨/시간대/테마 큐레이션까지 에이전트가 담당하도록 확장 가능해야 한다
  (현재 `.harness/PLAN.md` Task 11 큐레이션은 순수 함수 규칙 기반으로 설계되어
  있음 — 이걸 에이전트화할지는 이번 조사에서 판단하지 않고 "확장 가능한가"만 본다).

## 1. 기존 Protocol 기반 클라이언트를 버려야 하는가

**결론: 완전히 버릴 필요는 없다. 레이어가 다르므로 공존 가능하지만, 역할이 바뀐다.**

현재 구조(`infrastructure/llm/protocols.py`):

```python
class EmbeddingClient(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...

class ChatCompletionClient(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...
```

- `EmbeddingClient`는 Strands 도입 여부와 **무관하게 그대로 유지**할 수 있다.
  Strands의 `Agent`는 "대화형 LLM 호출 + 도구 사용"을 오케스트레이션하는
  레이어이고, 벡터 임베딩은 이 오케스트레이션과 관계없이 pgvector 검색을 위해
  독립적으로 필요하다. Strands SDK 자체가 임베딩 클라이언트 역할을 대체하지
  않는다. `MockEmbeddingClient`/`BedrockClient`(embed 부분)는 그대로 둔다.
- `ChatCompletionClient`(단순 `complete(messages) -> str`)는 Strands 도입 시
  **역할이 축소되거나 대체된다.** Strands의 `Agent`는 모델 호출 + 도구 선택 +
  멀티턴 루프까지를 캡슐화하므로, "메시지 목록을 넣으면 문자열 하나가 나온다"는
  현재 인터페이스보다 책임이 훨씬 크다. Strands를 도입하면 `ChatService`가
  `ChatCompletionClient.complete(...)`를 직접 호출하는 대신 `librarian_agent(message)`
  형태로 Strands `Agent`를 호출하게 된다.
  - `MockChatCompletionClient`는 테스트에서 Bedrock 실제 호출 없이 결정론적으로
    검증하는 용도로 계속 유용할 수 있다. Strands도 커스텀 모델 프로바이더를 꽂을
    수 있는 확장 지점을 제공하므로(`Agent(model=your_custom_model)`), 이 자리에
    Mock을 그대로 연결하는 방식으로 재사용 가능하다. [출처: Strands 공식 문서 —
    Custom Model Provider](https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/index.md)
- 정리: **`EmbeddingClient`는 유지, `ChatCompletionClient`는 Strands `Agent`/커스텀
  모델 프로바이더로 대체되는 것에 가깝다.** 완전 폐기가 아니라 "챗 완성"의 역할이
  Strands `Agent`로 옮겨가고, Mock 구현체는 커스텀 모델 프로바이더 형태로 재활용될
  여지가 있다.

## 2. Strands의 Agent/tool로 "사서 에이전트"를 어떻게 모델링할까 (초안)

Strands 공식 문서 기준 핵심 개념:

- `Agent`: 모델 + 도구 목록 + system prompt를 갖고, "모델을 호출 → 도구 선택 여부
  판단 → 필요하면 도구 실행 → 다시 모델 호출"을 반복하는 루프. [출처: Strands
  블로그 — Introducing Strands Agents](https://strandsagents.com/blog/introducing-strands-agents/index.md)
- `@tool` 데코레이터: 임의의 Python 함수를 도구로 등록. 클래스 메서드에 붙이면
  인스턴스 상태(예: DB 세션, 리포지토리)에 접근하는 도구를 만들 수 있다. [출처:
  Strands 공식 문서 — Creating Custom Tools](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/index.md)
- "Agents-as-tools" 패턴: 다른 `Agent` 인스턴스를 `@tool`로 감싸서 상위 오케스트레이터
  에이전트의 도구로 등록할 수 있다. [출처: Strands 블로그 — Strands Agents 1.0](https://strandsagents.com/blog/strands-agents-1-0/index.md)

### 초안 구조

```python
from strands import Agent, tool

# --- 공용 "추천" 도구: 페르소나와 무관하게 서비스 전체가 공유 ---

@tool
def search_books(query: str, top_k: int = 5) -> list[dict]:
    """자연어 질의로 pgvector 유사도 검색을 수행해 후보 도서를 반환한다.

    기존 BookRepository.search_by_embedding + EmbeddingClient.embed를
    그대로 감싼다. Strands 도입과 무관하게 이 두 컴포넌트는 유지된다.
    """
    ...  # EmbeddingClient.embed([query]) -> BookRepository.search_by_embedding(...)


# --- "사서" 페르소나 에이전트: system_prompt로 페르소나를 분리 ---

librarian_agent = Agent(
    name="librarian",
    system_prompt=(
        "당신은 도서관 사서입니다. 다정하고 신뢰감 있는 말투로 도서를 추천하세요. "
        "search_books 도구로 찾은 후보 중에서만 추천하고, 근거를 함께 제시하세요."
    ),
    tools=[search_books],
)

# --- 나중에 추가될 다른 페르소나 예시 (지금 구현하지 않음, 구조 확인용) ---

curator_agent = Agent(
    name="curator",
    system_prompt="당신은 테마 큐레이터입니다. 시간대/날씨에 맞는 도서를 제안하세요.",
    tools=[search_books, resolve_theme_tool, weather_tool],  # 미래 확장
)
```

- "추천 에이전트는 공용 하나": 위 예시에서 `search_books`가 그 역할이다.
  `@tool`로 정의된 순수 검색 로직은 페르소나에 종속되지 않고 여러 `Agent`
  (`librarian_agent`, 나중에 생길 `curator_agent` 등)가 동일하게 재사용한다.
  즉 "공용 추천 로직"은 에이전트가 아니라 **모든 페르소나 에이전트가 공유하는
  도구**로 모델링하는 것이 Strands의 관용적인 방식과 맞는다. 요청에서 말한
  "추천 에이전트 하나"를 Strands의 `Agent` 인스턴스로 만들 수도 있지만(예:
  `recommendation_agent`를 만들어 `librarian_agent`가 agents-as-tools 패턴으로
  호출), 검색 자체에 페르소나 판단이 필요 없다면 도구로 두는 편이 더 가볍다.
  이 판단(에이전트로 만들지 vs 도구로 둘지)은 설계 선택지이며 이번 조사에서
  결정하지 않는다.
- "사서 페르소나는 에이전트별로 분리": `Agent(system_prompt=...)`가 페르소나를
  결정하는 지점이다. 페르소나마다 별도 `Agent` 인스턴스(다른 `system_prompt`,
  선택적으로 다른 tools 조합)를 만들면 된다.
- "나중에 날씨/시간대/테마 큐레이션까지 에이전트가 담당": 위 `curator_agent`
  예시처럼 새 `Agent` + 새 `@tool`(예: `resolve_theme_tool`, `weather_tool`)을
  추가하는 방식으로 확장 가능하다. 여러 페르소나 에이전트를 하나의 상위
  오케스트레이터가 라우팅하게 하려면 Strands의 `Swarm`/`Graph`/"agents-as-tools"
  멀티 에이전트 패턴을 그대로 적용할 수 있다. [출처: Strands 공식 문서 —
  Multi-Agent Systems](https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/index.md)

## 3. CLIAR-51 Task 12(`/chat`)와의 통합 방식

두 가지 선택지가 있다. **이번 조사에서는 선택지만 제시하며, 어느 쪽으로 갈지는
결정하지 않는다.**

### 선택지 A — Task 12를 Strands 기반으로 다시 설계

- `ChatService.answer(...)`의 내부 구현을 Strands `Agent` 호출로 교체한다.
- 장점: 지금 당장 "사서 페르소나 분리 가능한 구조"를 갖추고 시작할 수 있다.
  나중에 페르소나가 추가될 때 `ChatService`를 다시 뜯어고칠 필요가 없다.
- 단점: CLIAR-51의 범위가 커진다. Task 12는 이미 "Redis 히스토리 로드 → 임베딩 →
  벡터 검색 → 프롬프트 조립 → LLM 호출 → 히스토리 append"라는 구체적인 파이프라인으로
  설계되어 있고(`.harness/PLAN.md`), Strands `Agent`의 도구 선택 루프는 이 흐름을
  에이전트에게 위임하는 방식이라 설계를 다시 검토해야 한다. Redis 히스토리를
  Strands의 대화 상태 관리와 어떻게 맞출지도 추가 조사가 필요하다(이번 조사에서는
  다루지 않음).

### 선택지 B — Task 12는 원안(Protocol 기반)대로 진행하고, Strands는 별도 티켓

- 지금 CLIAR-51 Task 12는 계획대로 `ChatCompletionClient` 기반으로 구현한다.
- Strands 도입은 별도 티켓에서, Task 12가 끝난 뒤 `ChatService` 내부를 Strands
  기반으로 교체하는 리팩터링으로 진행한다.
- 장점: CLIAR-51의 범위와 일정이 흔들리지 않는다. `/chat` API 계약
  (`docs/api/openapi.yaml`)은 이미 확정되어 있으므로, 내부 구현을 나중에
  Strands로 바꿔도 API 소비자(클라이언트)에는 영향이 없다.
- 단점: Task 12를 한 번 구현하고 나중에 다시 뜯어고치는 재작업 비용이 생긴다.

이 선택은 팀 논의 후 결정해달라고 하신 부분이라 이 문서에서는 판단하지 않는다.

## 종합 요약

| 질문 | 조사 결과 |
| --- | --- |
| Protocol 기반 클라이언트 폐기 여부 | `EmbeddingClient`는 유지. `ChatCompletionClient`는 Strands `Agent`/커스텀 모델 프로바이더로 대체되는 방향이며, Mock은 커스텀 모델 프로바이더로 재활용 가능 |
| 사서 에이전트 모델링 | `Agent(system_prompt=...)`로 페르소나 분리, 공용 검색 로직은 `@tool`로 여러 에이전트가 공유, 향후 페르소나 확장은 새 `Agent`+`@tool` 추가로 대응 |
| CLIAR-51 Task 12 통합 여부 | 선택지 A(지금 통합)/B(원안대로 진행 후 별도 티켓) 두 가지, 결정 필요 |

## 참고 자료

- [Strands 공식 블로그 — Introducing Strands Agents](https://strandsagents.com/blog/introducing-strands-agents/index.md)
- [Strands 공식 블로그 — Strands Agents 1.0 (Agents-as-tools, Swarm, Graph)](https://strandsagents.com/blog/strands-agents-1-0/index.md)
- [Strands 공식 문서 — Multi-Agent Systems](https://strandsagents.com/docs/user-guide/concepts/multi-agent/multi-agent-patterns/index.md)
- [Strands 공식 문서 — Creating Custom Tools](https://strandsagents.com/docs/user-guide/concepts/tools/custom-tools/index.md)
- [Strands 공식 문서 — Custom Model Provider](https://strandsagents.com/docs/user-guide/concepts/model-providers/custom_model_provider/index.md)
- [Strands 공식 Quickstart (Python)](https://strandsagents.com/docs/user-guide/quickstart/python/index.md)

이 문서는 `.harness/research/`에 조사 결과로만 보관한다. 코드는 작성하지 않았다.
결정이 확정되면 `.harness/DECISIONS.md`에 결정 사항과 근거를 옮겨 기록하고,
CLIAR-51 이후 별도 티켓으로 이어갈지는 그때 `.harness/PLAN.md`에 반영한다.
