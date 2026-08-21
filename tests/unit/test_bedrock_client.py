"""BedrockClient의 요청 조립/응답 파싱을 검증한다.

boto3.client 자체를 mocker.patch로 대체하므로, 이 테스트는 실제 AWS API를
호출하지 않는다 (네트워크 요청, AWS 자격증명, 비용 모두 발생하지 않음).
"""

import io
import json

import pytest
from pytest_mock import MockerFixture

from discovery.infrastructure.llm.bedrock_client import (
    CHAT_MODEL_ID,
    EMBEDDING_MODEL_ID,
    BedrockClient,
)


def _make_invoke_model_response(payload: dict[str, object]) -> dict[str, object]:
    return {"body": io.BytesIO(json.dumps(payload).encode("utf-8"))}


def test_embed_calls_invoke_model_with_titan_embed_payload(mocker: MockerFixture) -> None:
    mock_boto_client = mocker.Mock()
    mock_boto_client.invoke_model.return_value = _make_invoke_model_response(
        {"embedding": [0.1, 0.2, 0.3]}
    )
    mock_boto3_client = mocker.patch(
        "discovery.infrastructure.llm.bedrock_client.boto3.client",
        return_value=mock_boto_client,
    )

    client = BedrockClient(region_name="us-east-1")
    result = client.embed(["안녕하세요"])

    # boto3.client 생성 자체가 patch됐으므로 실제 AWS 연결은 시도되지 않는다.
    mock_boto3_client.assert_called_once_with("bedrock-runtime", region_name="us-east-1")
    mock_boto_client.invoke_model.assert_called_once_with(
        modelId=EMBEDDING_MODEL_ID,
        body=json.dumps({"inputText": "안녕하세요"}),
        contentType="application/json",
        accept="application/json",
    )
    assert result == [[0.1, 0.2, 0.3]]


def test_embed_raises_when_response_missing_embedding_field(mocker: MockerFixture) -> None:
    mock_boto_client = mocker.Mock()
    mock_boto_client.invoke_model.return_value = _make_invoke_model_response({"unexpected": True})
    mocker.patch(
        "discovery.infrastructure.llm.bedrock_client.boto3.client",
        return_value=mock_boto_client,
    )

    client = BedrockClient(region_name="us-east-1")

    with pytest.raises(ValueError, match="embedding"):
        client.embed(["텍스트"])


def test_complete_calls_invoke_model_with_claude_payload(mocker: MockerFixture) -> None:
    mock_boto_client = mocker.Mock()
    mock_boto_client.invoke_model.return_value = _make_invoke_model_response(
        {"content": [{"type": "text", "text": "추천 답변입니다."}]}
    )
    mocker.patch(
        "discovery.infrastructure.llm.bedrock_client.boto3.client",
        return_value=mock_boto_client,
    )

    client = BedrockClient(region_name="us-east-1")
    messages = [{"role": "user", "content": "소설 추천해줘"}]
    result = client.complete(messages)

    mock_boto_client.invoke_model.assert_called_once_with(
        modelId=CHAT_MODEL_ID,
        body=json.dumps(
            {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 1024,
                "messages": messages,
            }
        ),
        contentType="application/json",
        accept="application/json",
    )
    assert result == "추천 답변입니다."


def test_complete_raises_when_response_missing_content_field(mocker: MockerFixture) -> None:
    mock_boto_client = mocker.Mock()
    mock_boto_client.invoke_model.return_value = _make_invoke_model_response({"unexpected": True})
    mocker.patch(
        "discovery.infrastructure.llm.bedrock_client.boto3.client",
        return_value=mock_boto_client,
    )

    client = BedrockClient(region_name="us-east-1")

    with pytest.raises(ValueError, match="content"):
        client.complete([{"role": "user", "content": "질문"}])
