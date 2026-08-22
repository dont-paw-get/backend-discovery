"""LLM_PROVIDER 설정값에 따라 Mock 또는 Bedrock 구현을 선택하는 팩토리.

기본값은 mock이다 (.harness/DECISIONS.md 참고 — 별도 USE_REAL_BEDROCK 플래그를
추가하지 않고 LLM_PROVIDER를 단일 소스로 유지한다).
"""

from discovery.core.config import Settings
from discovery.infrastructure.llm.bedrock_client import BedrockClient
from discovery.infrastructure.llm.mock_bedrock import (
    MockChatCompletionClient,
    MockEmbeddingClient,
)
from discovery.infrastructure.llm.protocols import ChatCompletionClient, EmbeddingClient

_SUPPORTED_PROVIDERS = ("mock", "bedrock")


def _validate_provider(settings: Settings) -> str:
    provider = settings.llm_provider
    if provider not in _SUPPORTED_PROVIDERS:
        raise ValueError(
            f"지원하지 않는 LLM_PROVIDER 값입니다: {provider!r} "
            f"(가능한 값: {_SUPPORTED_PROVIDERS})"
        )
    return provider


def create_embedding_client(settings: Settings) -> EmbeddingClient:
    provider = _validate_provider(settings)
    if provider == "bedrock":
        if not settings.aws_region:
            raise ValueError("LLM_PROVIDER=bedrock이면 AWS_REGION이 설정되어 있어야 합니다")
        return BedrockClient(region_name=settings.aws_region)
    return MockEmbeddingClient()


def create_chat_completion_client(settings: Settings) -> ChatCompletionClient:
    provider = _validate_provider(settings)
    if provider == "bedrock":
        if not settings.aws_region:
            raise ValueError("LLM_PROVIDER=bedrock이면 AWS_REGION이 설정되어 있어야 합니다")
        return BedrockClient(region_name=settings.aws_region)
    return MockChatCompletionClient()
