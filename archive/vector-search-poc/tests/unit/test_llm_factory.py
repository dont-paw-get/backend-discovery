"""LLM_PROVIDER 설정값에 따라 factory가 올바른 구현을 선택하는지 검증한다.

bedrock 케이스도 boto3.client를 patch하므로 실제 AWS 호출은 발생하지 않는다.
"""

import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.infrastructure.llm.bedrock_client import BedrockClient
from discovery.infrastructure.llm.factory import (
    create_chat_completion_client,
    create_embedding_client,
)
from discovery.infrastructure.llm.mock_bedrock import (
    MockChatCompletionClient,
    MockEmbeddingClient,
)


def _make_settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "database_url": "postgresql+asyncpg://test",
        "redis_url": "redis://test",
        "internal_api_token": "test-token",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def test_create_embedding_client_defaults_to_mock() -> None:
    settings = _make_settings()

    client = create_embedding_client(settings)

    assert isinstance(client, MockEmbeddingClient)


def test_create_chat_completion_client_defaults_to_mock() -> None:
    settings = _make_settings()

    client = create_chat_completion_client(settings)

    assert isinstance(client, MockChatCompletionClient)


def test_create_embedding_client_returns_bedrock_when_configured(mocker: MockerFixture) -> None:
    mocker.patch("discovery.infrastructure.llm.bedrock_client.boto3.client")
    settings = _make_settings(llm_provider="bedrock", aws_region="us-east-1")

    client = create_embedding_client(settings)

    assert isinstance(client, BedrockClient)


def test_create_embedding_client_bedrock_without_region_raises() -> None:
    settings = _make_settings(llm_provider="bedrock", aws_region=None)

    with pytest.raises(ValueError, match="AWS_REGION"):
        create_embedding_client(settings)


def test_create_embedding_client_unknown_provider_raises() -> None:
    settings = _make_settings(llm_provider="unknown")

    with pytest.raises(ValueError, match="LLM_PROVIDER"):
        create_embedding_client(settings)
