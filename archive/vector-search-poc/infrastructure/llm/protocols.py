"""LLM/임베딩 클라이언트의 추상 인터페이스. Mock과 Bedrock 구현이 이 Protocol을 따른다.

LLM_PROVIDER 설정값(core/config.py)으로 구현을 교체할 수 있게 하기 위한 경계다.
"""

from typing import Protocol


class EmbeddingClient(Protocol):
    """텍스트를 벡터로 임베딩하는 클라이언트."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        """각 텍스트를 동일한 차원의 벡터로 변환한다. 입력과 출력의 길이가 같다."""
        ...


class ChatCompletionClient(Protocol):
    """대화 메시지로부터 응답 텍스트를 생성하는 클라이언트."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        """`{"role": ..., "content": ...}` 형태의 메시지 목록을 받아 응답 문자열을 반환한다."""
        ...
