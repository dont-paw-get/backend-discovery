"""사서 에이전트 팩토리(create_librarian_agent)의 생성 결과를 검증한다.

Bedrock 실제 호출은 발생시키지 않는다: BedrockModel 생성 자체를 mocker로 대체해
boto3 클라이언트를 만들지 않게 한다(AWS 자격증명 unset 상태에서도 통과해야 한다).
"""

from pytest_mock import MockerFixture

from discovery.domain.librarian.agent import LIBRARIAN_SYSTEM_PROMPT, create_librarian_agent

# 교육 계정에서 실제 호출 가능 확인된 모델(.harness/BACKLOG.md 참고).
CLAUDE_3_HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


def test_create_librarian_agent_uses_configured_model_id(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.librarian.agent.BedrockModel")

    create_librarian_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID)

    bedrock_model_cls.assert_called_once_with(model_id=CLAUDE_3_HAIKU_MODEL_ID, region_name=None)


def test_create_librarian_agent_passes_region_name(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.librarian.agent.BedrockModel")

    create_librarian_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID, region_name="us-east-1")

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_3_HAIKU_MODEL_ID, region_name="us-east-1"
    )


def test_create_librarian_agent_sets_librarian_system_prompt(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.librarian.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.librarian.agent.Agent")

    create_librarian_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID)

    _, kwargs = agent_cls.call_args
    assert kwargs["system_prompt"] == LIBRARIAN_SYSTEM_PROMPT


def test_create_librarian_agent_returns_agent_instance(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.librarian.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.librarian.agent.Agent")
    agent_cls.return_value = mocker.sentinel.agent

    result = create_librarian_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID)

    assert result is mocker.sentinel.agent
