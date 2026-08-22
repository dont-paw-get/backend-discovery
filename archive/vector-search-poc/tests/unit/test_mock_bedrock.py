"""MockEmbeddingClient/MockChatCompletionClient의 결정론성을 검증한다.

boto3를 전혀 사용하지 않으므로 별도 mocking 없이도 실제 API 호출이 발생하지 않는다.
"""

import math

from discovery.infrastructure.llm.mock_bedrock import (
    EMBEDDING_DIM,
    MockChatCompletionClient,
    MockEmbeddingClient,
)


def test_embed_is_deterministic_for_same_input() -> None:
    client = MockEmbeddingClient()

    first = client.embed(["안녕하세요"])
    second = client.embed(["안녕하세요"])

    assert first == second


def test_embed_returns_correct_dimension() -> None:
    client = MockEmbeddingClient()

    [vector] = client.embed(["임의의 텍스트"])

    assert len(vector) == EMBEDDING_DIM == 1536


def test_embed_vector_is_l2_normalized() -> None:
    client = MockEmbeddingClient()

    [vector] = client.embed(["정규화 검증용 텍스트"])
    norm = math.sqrt(sum(x * x for x in vector))

    assert math.isclose(norm, 1.0, rel_tol=1e-9)


def test_embed_differs_for_different_input() -> None:
    client = MockEmbeddingClient()

    [vector_a] = client.embed(["텍스트 A"])
    [vector_b] = client.embed(["텍스트 B"])

    assert vector_a != vector_b


def test_embed_handles_multiple_texts_in_order() -> None:
    client = MockEmbeddingClient()

    vectors = client.embed(["첫 번째", "두 번째"])
    [vector_first] = client.embed(["첫 번째"])
    [vector_second] = client.embed(["두 번째"])

    assert vectors[0] == vector_first
    assert vectors[1] == vector_second


def test_complete_returns_librarian_persona_response() -> None:
    client = MockChatCompletionClient()

    response = client.complete([{"role": "user", "content": "따뜻한 소설 추천해줘"}])

    assert "사서" in response
