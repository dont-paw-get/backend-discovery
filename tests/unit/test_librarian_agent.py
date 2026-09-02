"""추천 에이전트 팩토리(create_librarian_agent)의 생성 결과를 검증한다.

Bedrock 실제 호출은 발생시키지 않는다: BedrockModel 생성 자체를 mocker로 대체해
boto3 클라이언트를 만들지 않게 한다(AWS 자격증명 unset 상태에서도 통과해야 한다).
"""

from pytest_mock import MockerFixture
from strands.models.model import CacheConfig

from discovery.domain.librarian.agent import LIBRARIAN_SYSTEM_PROMPT, create_librarian_agent

CLAUDE_SONNET_5_MODEL_ID = "global.anthropic.claude-sonnet-5"


def test_create_librarian_agent_uses_configured_model_id(
    mocker: MockerFixture,
) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.librarian.agent.BedrockModel")

    create_librarian_agent(model_id=CLAUDE_SONNET_5_MODEL_ID)

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name=None,
        max_tokens=1536,
        top_p=0.9,
    )


def test_create_librarian_agent_passes_region_name(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.librarian.agent.BedrockModel")

    create_librarian_agent(model_id=CLAUDE_SONNET_5_MODEL_ID, region_name="us-east-1")

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name="us-east-1",
        max_tokens=1536,
        top_p=0.9,
    )


def test_create_librarian_agent_with_prompt_caching(mocker: MockerFixture) -> None:
    bedrock_model_cls = mocker.patch("discovery.domain.librarian.agent.BedrockModel")

    create_librarian_agent(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name="us-east-1",
        enable_prompt_caching=True,
    )

    bedrock_model_cls.assert_called_once_with(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        region_name="us-east-1",
        max_tokens=1536,
        top_p=0.9,
        cache_config=CacheConfig(strategy="auto"),
        cache_tools="default",
    )


def test_create_librarian_agent_sets_librarian_system_prompt(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.librarian.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.librarian.agent.Agent")

    create_librarian_agent(model_id=CLAUDE_SONNET_5_MODEL_ID)

    _, kwargs = agent_cls.call_args
    assert kwargs["system_prompt"] == LIBRARIAN_SYSTEM_PROMPT


def test_create_librarian_agent_returns_agent_instance(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.librarian.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.librarian.agent.Agent")
    agent_cls.return_value = mocker.sentinel.agent

    result = create_librarian_agent(model_id=CLAUDE_SONNET_5_MODEL_ID)

    assert result is mocker.sentinel.agent


def test_create_librarian_agent_passes_tools_and_messages(mocker: MockerFixture) -> None:
    mocker.patch("discovery.domain.librarian.agent.BedrockModel")
    agent_cls = mocker.patch("discovery.domain.librarian.agent.Agent")

    mock_tool = mocker.MagicMock()
    mock_messages = [{"role": "user", "content": [{"text": "hello"}]}]

    create_librarian_agent(
        model_id=CLAUDE_SONNET_5_MODEL_ID,
        tools=[mock_tool],
        messages=mock_messages,
    )

    _, kwargs = agent_cls.call_args
    assert kwargs["tools"] == [mock_tool]
    assert kwargs["messages"] == mock_messages


def test_librarian_system_prompt_contains_structured_markdown_template() -> None:
    assert "### 📖" in LIBRARIAN_SYSTEM_PROMPT
    assert "- **저자**:" in LIBRARIAN_SYSTEM_PROMPT
    assert "({페이지수}쪽)" in LIBRARIAN_SYSTEM_PROMPT
    assert "- **추천 이유**:" in LIBRARIAN_SYSTEM_PROMPT
    assert "search_books" in LIBRARIAN_SYSTEM_PROMPT
    assert "권수" in LIBRARIAN_SYSTEM_PROMPT
    assert "쪽수" in LIBRARIAN_SYSTEM_PROMPT
    assert "줄거리" in LIBRARIAN_SYSTEM_PROMPT
    assert "스포일러" in LIBRARIAN_SYSTEM_PROMPT
    assert "톤앤매너" in LIBRARIAN_SYSTEM_PROMPT
    assert "해외 도서 번역" in LIBRARIAN_SYSTEM_PROMPT
    assert "한국어 표준 명칭" in LIBRARIAN_SYSTEM_PROMPT
    assert "원작자" in LIBRARIAN_SYSTEM_PROMPT


def test_get_librarian_system_prompt_by_librarian_id() -> None:
    from discovery.domain.librarian.agent import get_librarian_system_prompt

    cat_prompt = get_librarian_system_prompt("cat")
    assert "블루" in cat_prompt

    stork_prompt = get_librarian_system_prompt("stork")
    assert "슈빌" in stork_prompt
    assert "고양이 말투는 사용하지 않습니다" in stork_prompt
