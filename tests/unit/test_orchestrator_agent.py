"""오케스트레이터 에이전트 팩토리(create_orchestrator_agent)의 생성 결과를 검증한다.

Bedrock 실제 호출은 발생시키지 않는다: BedrockModel 생성 자체를 mocker로 대체해
boto3 클라이언트를 만들지 않게 한다(AWS 자격증명 unset 상태에서도 통과해야 한다).
"""

from pytest_mock import MockerFixture
from strands.models.model import CacheConfig

from discovery.domain.orchestrator.agent import (
    ORCHESTRATOR_SYSTEM_PROMPT,
    create_orchestrator_agent,
)

CLAUDE_3_HAIKU_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


def test_create_orchestrator_agent_uses_configured_model_id(
    mocker: MockerFixture,
) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")

    create_orchestrator_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID)

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_3_HAIKU_MODEL_ID,
        region_name=None,
    )


def test_create_orchestrator_agent_passes_region_name(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")

    create_orchestrator_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID, region_name="us-east-1")

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_3_HAIKU_MODEL_ID,
        region_name="us-east-1",
    )


def test_create_orchestrator_agent_with_prompt_caching(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")

    create_orchestrator_agent(
        model_id=CLAUDE_3_HAIKU_MODEL_ID,
        region_name="us-east-1",
        enable_prompt_caching=True,
    )

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_3_HAIKU_MODEL_ID,
        region_name="us-east-1",
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
    )


def test_create_orchestrator_agent_sets_orchestrator_system_prompt(
    mocker: MockerFixture,
) -> None:
    mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.orchestrator.agent.Agent")

    create_orchestrator_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID)

    _, kwargs = agent_cls.call_args
    assert kwargs["system_prompt"] == ORCHESTRATOR_SYSTEM_PROMPT


def test_create_orchestrator_agent_returns_agent_instance(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.orchestrator.agent.Agent")
    agent_cls.return_value = mocker.sentinel.agent

    result = create_orchestrator_agent(model_id=CLAUDE_3_HAIKU_MODEL_ID)

    assert result is mocker.sentinel.agent


def test_create_orchestrator_agent_passes_tools_and_messages(
    mocker: MockerFixture,
) -> None:
    mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.orchestrator.agent.Agent")

    mock_tool = mocker.MagicMock()
    mock_messages = [{"role": "user", "content": [{"text": "hello"}]}]

    create_orchestrator_agent(
        model_id=CLAUDE_3_HAIKU_MODEL_ID,
        tools=[mock_tool],
        messages=mock_messages,
    )

    _, kwargs = agent_cls.call_args
    assert kwargs["tools"] == [mock_tool]
    assert kwargs["messages"] == mock_messages


def test_orchestrator_system_prompt_contains_rules() -> None:
    assert "recommend_books" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "consult_librarian" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "위임" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "count" in ORCHESTRATOR_SYSTEM_PROMPT or "권수" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "과잉 사과 금지" in ORCHESTRATOR_SYSTEM_PROMPT
