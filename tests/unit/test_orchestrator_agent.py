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

CLAUDE_SONNET_5_MODEL_ID = "global.anthropic.claude-sonnet-5"


def test_create_orchestrator_agent_uses_configured_model_id(
    mocker: MockerFixture,
) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")

    create_orchestrator_agent(model_id=CLAUDE_SONNET_5_MODEL_ID)

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name=None,
        max_tokens=2048,
    )


def test_create_orchestrator_agent_passes_region_name(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")

    create_orchestrator_agent(model_id=CLAUDE_SONNET_5_MODEL_ID, region_name="us-east-1")

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name="us-east-1",
        max_tokens=2048,
    )


def test_create_orchestrator_agent_with_prompt_caching(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")

    create_orchestrator_agent(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name="us-east-1",
        enable_prompt_caching=True,
    )

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name="us-east-1",
        max_tokens=2048,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
    )


def test_create_orchestrator_agent_sets_orchestrator_system_prompt(
    mocker: MockerFixture,
) -> None:
    mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.orchestrator.agent.Agent")

    create_orchestrator_agent(model_id=CLAUDE_SONNET_5_MODEL_ID)

    _, kwargs = agent_cls.call_args
    assert kwargs["system_prompt"] == ORCHESTRATOR_SYSTEM_PROMPT


def test_create_orchestrator_agent_returns_agent_instance(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.orchestrator.agent.Agent")
    agent_cls.return_value = mocker.sentinel.agent

    result = create_orchestrator_agent(model_id=CLAUDE_SONNET_5_MODEL_ID)

    assert result is mocker.sentinel.agent


def test_create_orchestrator_agent_passes_tools_and_messages(
    mocker: MockerFixture,
) -> None:
    mocker.patch("discovery.domain.orchestrator.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.orchestrator.agent.Agent")

    mock_tool = mocker.MagicMock()
    mock_messages = [{"role": "user", "content": [{"text": "hello"}]}]

    create_orchestrator_agent(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        tools=[mock_tool],
        messages=mock_messages,
    )

    _, kwargs = agent_cls.call_args
    assert kwargs["tools"] == [mock_tool]
    assert kwargs["messages"] == mock_messages


def test_orchestrator_system_prompt_contains_rules() -> None:
    assert "recommend_books" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "consult_librarian" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "search_my_library" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "서재 안내 지침" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "위임" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "count" in ORCHESTRATOR_SYSTEM_PROMPT or "권수" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "사서 분석 정보" in ORCHESTRATOR_SYSTEM_PROMPT
    assert "과잉 사과 금지" in ORCHESTRATOR_SYSTEM_PROMPT


def test_get_orchestrator_system_prompt_by_librarian_id() -> None:
    from discovery.domain.orchestrator.agent import get_orchestrator_system_prompt

    # 1. cat 사서: 블루 페르소나, ~다냥, 미스터리 특화
    cat_prompt = get_orchestrator_system_prompt("cat")
    assert "블루" in cat_prompt
    assert "~다냥" in cat_prompt or "고양이" in cat_prompt
    assert "슈빌" in cat_prompt

    # 2. stork 사서: 슈빌 페르소나, 두둥, 존댓말, 고양이 말투 배제
    stork_prompt = get_orchestrator_system_prompt("stork")
    assert "슈빌" in stork_prompt
    assert "두둥" in stork_prompt
    assert "고양이 말투" in stork_prompt
    assert "블루" in stork_prompt
