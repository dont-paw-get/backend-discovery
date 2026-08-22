"""추천 에이전트(Librarian 페르소나). Strands Agents SDK 기반.

CLIAR-51 Task 1(스모크 테스트) 범위: 도구 없이 system_prompt만 가진 최소 에이전트를
만들어 Strands SDK 도입이 정상 동작하는지 확인한다. 웹 검색 도구(Tavily) 연동은
Task 2에서 추가한다.

향후 다른 페르소나(예: 테마 큐레이터)가 추가될 때는 이 모듈과 같은 패턴으로
`domain/<페르소나명>/agent.py`에 별도 팩토리를 두는 것을 지향한다
(.harness/research/2026-08-21-strands-agents-poc-design.md 참고).
"""

from typing import Any

from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig

LIBRARIAN_SYSTEM_PROMPT = (
    "당신은 다정하고 신뢰감 있는 도서관 사서입니다. "
    "사용자의 질문이나 관심사에 맞는 도서를 추천하고, 추천 이유를 친절하게 설명하세요. "
    "도서 정보가 필요하거나 추천 후보를 찾을 때는 search_books 도구를 적극 활용하세요."
)


def create_librarian_agent(
    *,
    model_id: str,
    region_name: str | None = None,
    tools: list[Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    system_prompt: str = LIBRARIAN_SYSTEM_PROMPT,
    enable_prompt_caching: bool = False,
) -> Agent:
    """추천 에이전트를 생성한다.

    Args:
        model_id: Bedrock 모델 ID (core/config.py의 Settings.librarian_model_id).
        region_name: AWS 리전. None이면 boto3 기본 설정(환경 변수/프로파일)을 따른다.
        tools: 에이전트에 등록할 도구 목록 (예: BookSearchTool.as_tool()).
        messages: 이전 대화 히스토리 (ChatSessionStore에서 불러온 내역을
            Strands 형식으로 변환한 것).
        system_prompt: 시스템 프롬프트.
        enable_prompt_caching: Bedrock 자동 프롬프트 캐싱 활성화 여부 (지원 모델만 사용).
    """
    model_kwargs: dict[str, Any] = {
        "model_id": model_id,
        "region_name": region_name,
    }
    if enable_prompt_caching:
        model_kwargs["cache_config"] = CacheConfig(strategy="auto")
        model_kwargs["cache_tools"] = "default"

    model = BedrockModel(**model_kwargs)
    kwargs: dict[str, Any] = {
        "model": model,
        "system_prompt": system_prompt,
    }
    if tools is not None:
        kwargs["tools"] = tools
    if messages is not None:
        kwargs["messages"] = messages
    return Agent(**kwargs)
