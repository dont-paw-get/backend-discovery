"""사서(Librarian) 페르소나 에이전트. Strands Agents SDK 기반.

CLIAR-51 Task 1(스모크 테스트) 범위: 도구 없이 system_prompt만 가진 최소 에이전트를
만들어 Strands SDK 도입이 정상 동작하는지 확인한다. 웹 검색 도구(Tavily) 연동은
Task 2에서 추가한다.

향후 다른 페르소나(예: 테마 큐레이터)가 추가될 때는 이 모듈과 같은 패턴으로
`domain/<페르소나명>/agent.py`에 별도 팩토리를 두는 것을 지향한다
(.harness/research/2026-08-21-strands-agents-poc-design.md 참고).
"""

from strands import Agent
from strands.models import BedrockModel

LIBRARIAN_SYSTEM_PROMPT = (
    "당신은 다정하고 신뢰감 있는 도서관 사서입니다. "
    "사용자의 질문에 친절한 말투로 도서를 추천하고, 추천 이유를 함께 설명하세요."
)


def create_librarian_agent(*, model_id: str, region_name: str | None = None) -> Agent:
    """사서 페르소나 에이전트를 생성한다. 도구는 아직 연결하지 않는다(Task 2에서 추가).

    Args:
        model_id: Bedrock 모델 ID (core/config.py의 Settings.librarian_model_id).
        region_name: AWS 리전. None이면 boto3 기본 설정(환경 변수/프로파일)을 따른다.
    """
    model = BedrockModel(model_id=model_id, region_name=region_name)
    return Agent(model=model, system_prompt=LIBRARIAN_SYSTEM_PROMPT)
