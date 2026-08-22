"""AWS Bedrock 실 연동 클라이언트. LLM_PROVIDER=bedrock일 때 factory.py가 이 구현을 선택한다.

boto3.client("bedrock-runtime")을 생성해 invoke_model을 호출한다. 단위 테스트는
boto3.client 자체를 mocker.patch로 대체해 실제 AWS API를 호출하지 않는다.
"""

import json

import boto3
from mypy_boto3_bedrock_runtime import BedrockRuntimeClient

EMBEDDING_MODEL_ID = "amazon.titan-embed-text-v1"
CHAT_MODEL_ID = "anthropic.claude-3-haiku-20240307-v1:0"


class BedrockClient:
    """AWS Bedrock Runtime을 사용하는 임베딩/챗 완성 클라이언트."""

    def __init__(self, region_name: str) -> None:
        self._client: BedrockRuntimeClient = boto3.client(
            "bedrock-runtime", region_name=region_name
        )

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        response = self._client.invoke_model(
            modelId=EMBEDDING_MODEL_ID,
            body=json.dumps({"inputText": text}),
            contentType="application/json",
            accept="application/json",
        )
        payload = json.loads(response["body"].read())
        embedding = payload.get("embedding")
        if not isinstance(embedding, list):
            raise ValueError(f"Bedrock 응답에 embedding 필드가 없습니다: {payload}")
        return embedding

    def complete(self, messages: list[dict[str, str]]) -> str:
        response = self._client.invoke_model(
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
        payload = json.loads(response["body"].read())
        content = payload.get("content")
        if not isinstance(content, list) or not content:
            raise ValueError(f"Bedrock 응답에 content 필드가 없습니다: {payload}")
        text = content[0]["text"]
        if not isinstance(text, str):
            raise ValueError(f"Bedrock 응답의 content[0].text가 문자열이 아닙니다: {payload}")
        return text
