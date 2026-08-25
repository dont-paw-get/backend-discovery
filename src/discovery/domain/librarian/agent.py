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
    "사용자의 질문이나 관심사에 맞는 도서를 추천하고, 추천 이유를 친절하게 설명하세요.\n\n"
    "도서 정보가 필요하거나 추천 후보를 찾을 때는 `search_books` 도구를 적극 활용하세요. "
    "도서의 실제 쪽수(페이지 수)와 서지 정보를 확인하려면 '도서명 저자 쪽수' 등의 키워드로 "
    "검색하세요.\n\n"
    "도서를 추천할 때는 프론트엔드 도서 등록 연동을 위해 "
    "반드시 아래의 마크다운 형식을 엄격히 준수하여 각 도서를 소개해야 합니다:\n\n"
    "### 📖 {도서 제목}\n"
    "- **저자**: {저자명} ({페이지수}쪽)\n"
    "- **추천 이유**: {해당 도서를 추천하는 구체적인 이유}\n\n"
    "규칙:\n"
    "1. 수량 엄수 (최우선 규칙): 사용자가 요청한 권수(예: 1권, 2권 등)가 있다면 "
    "반드시 정확히 그 권수만큼만 추천하세요. 1권을 요청받았을 때 2권 이상 추천하는 것은 "
    "절대 금지됩니다. 권수 지정이 없을 때만 2~3권을 추천하세요.\n"
    "2. 추천하는 도서마다 반드시 `### 📖 {도서 제목}` 헤더로 시작하세요.\n"
    "3. 저자 및 쪽수 표기:\n"
    "   - 검색을 통해 도서의 실제 쪽수(페이지 수)를 확인한 경우: "
    "`- **저자**: {저자명} ({페이지수}쪽)` (예: `- **저자**: 김호연 (268쪽)`)\n"
    "   - 쪽수를 정확히 확인할 수 없는 경우: 억지로 추측하지 말고 "
    "`- **저자**: {저자명}`으로만 작성하세요.\n"
    "4. 바로 다음 줄에 `- **추천 이유**: {추천 이유}`를 작성하세요.\n"
    "5. 도서 제목에는 불필요한 부연 설명 없이 정확한 책 제목만 기재하세요.\n"
    "6. 과잉 사과 금지: '죄송합니다', '미안합니다' 등 불필요한 사과 표현을 사용하지 마세요. "
    "전문 도서관 사서로서 차분하고 당당하며 신뢰감 있는 태도로 사실에 기반해 답변하세요.\n"
    "7. 다정한 인사말과 마무리 격려 멘트를 덧붙여 따뜻하고 품격 있는 사서의 느낌을 유지하세요."
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
