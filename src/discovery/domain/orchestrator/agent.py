"""오케스트레이터 에이전트. Strands Agents SDK 기반.

사용자의 의도를 분석하여 도서 추천 에이전트(로컬 도구) 또는 사서 에이전트(원격 도구)로
위임하는 최상위 오케스트레이션 역할을 담당한다.
"""

from typing import Any

from strands import Agent
from strands.models import BedrockModel
from strands.models.model import CacheConfig

ORCHESTRATOR_SYSTEM_PROMPT = (
    "당신은 Don't Paw Get Your Book의 총괄 안내 오케스트레이터 에이전트입니다. "
    "사용자의 질문과 대화 맥락을 파악하여 적절한 전문 도구를 활용하거나 직접 "
    "친절하게 응대하세요.\n\n"
    "도구 사용 규칙:\n"
    "1. 도서 추천 및 검색 요청: 특정 상황, 분위기, 장르, 주제에 맞는 책 추천이나 "
    "도서 정보 조사는 `recommend_books` 도구를 호출하세요.\n"
    "2. 사서와의 대화 및 상담: 도서관 사서와의 깊은 대화, 감정 및 독서 고민 상담 등은 "
    "`consult_librarian` 도구를 호출하세요.\n"
    "3. 도구 결과 처리: 도구 실행 결과가 '준비 중'이거나 오류 메시지인 경우, "
    "사용자에게 해당 기능을 현재 준비 중임을 다정하게 안내하고 도서 추천 등 가능한 "
    "대안을 제시하세요.\n"
    "4. 일반 대화: 단순 인사, 시스템 사용법 안내 등은 도구 호출 없이 직접 친절하게 답변하세요."
)


def create_orchestrator_agent(
    *,
    model_id: str,
    region_name: str | None = None,
    tools: list[Any] | None = None,
    messages: list[dict[str, Any]] | None = None,
    system_prompt: str = ORCHESTRATOR_SYSTEM_PROMPT,
    enable_prompt_caching: bool = False,
) -> Agent:
    """오케스트레이터 에이전트를 생성한다.

    Args:
        model_id: Bedrock 모델 ID (core/config.py의 Settings.orchestrator_model_id).
        region_name: AWS 리전. None이면 boto3 기본 설정을 따른다.
        tools: 에이전트에 등록할 도구 목록 (recommend_books_tool, consult_librarian_tool 등).
        messages: 이전 대화 히스토리 (ChatSessionStore에서 불러온 내역을 Strands 형식으로 변환).
        system_prompt: 오케스트레이터 시스템 프롬프트.
        enable_prompt_caching: Bedrock 자동 프롬프트 캐싱 활성화 여부.
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
