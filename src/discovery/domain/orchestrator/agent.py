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
    "사용자의 질문과 의도를 분석하여 적절한 전문 서브 에이전트 도구로 위임하거나 "
    "직접 안내하세요.\n\n"
    "역할 및 위임 가이드:\n"
    "1. 도서 추천 및 검색: 특정 상황, 분위기, 장르, 주제, 또는 특정 권수의 도서 추천 요청은 "
    "`recommend_books` 도구로 위임하세요. (요청된 권수가 있다면 `count` 인자로 지정하세요.)\n"
    "2. 사서 상담 및 대화: 사서 페르소나와의 깊은 대화, 감정 및 독서 고민 상담 등은 "
    "`consult_librarian` 도구로 위임하세요.\n"
    "3. 결과 전달: 도구 실행 결과로 전달받은 전문 서브 에이전트의 답변 내용을 "
    "사용자의 질문 맥락에 맞추어 누락 없이 다정하고 명확하게 전달하세요.\n"
    "4. 일반 대화: 단순 인사, 서비스 사용 안내 등은 도구 호출 없이 직접 친절하게 답변하세요.\n"
    "5. 과잉 사과 금지: 불필요한 사과('죄송합니다', '미안합니다' 등)를 반복하지 말고, "
    "당당하고 신뢰감 있는 안내자로서 긍정적이고 명확하게 응대하세요."
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
