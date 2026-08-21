"""Bedrock Mock 구현. AWS 미연동 상태에서도 결정론적으로 임베딩/챗 응답을 낸다.

같은 입력에는 항상 같은 벡터를 반환해야 테스트와 개발 경험이 예측 가능하다.
실제 Bedrock 호출은 BedrockClient(bedrock_client.py)가 담당한다.
"""

import hashlib
import random

EMBEDDING_DIM = 1536

_LIBRARIAN_PERSONA_TEMPLATE = (
    "저는 이 서재의 사서입니다. 말씀하신 내용을 살펴보니 다음 책들을 추천드리고 싶습니다:\n"
    "{book_titles}\n"
    "천천히 골라보시고, 더 궁금한 점이 있으면 언제든 물어보세요."
)


def _text_to_seed(text: str) -> int:
    """텍스트를 결정론적인 정수 시드로 변환한다. Python 프로세스 간에도 항상 같은 값이다."""
    digest = hashlib.sha256(text.encode("utf-8")).digest()
    return int.from_bytes(digest[:8], byteorder="big")


class MockEmbeddingClient:
    """입력 문자열 해시를 시드로 결정론적인 정규화 벡터를 생성하는 Mock 임베딩 클라이언트."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [self._embed_one(text) for text in texts]

    def _embed_one(self, text: str) -> list[float]:
        rng = random.Random(_text_to_seed(text))  # noqa: S311 (결정론적 재현성 목적, 암호화 용도 아님)
        raw_vector = [rng.uniform(-1.0, 1.0) for _ in range(EMBEDDING_DIM)]
        norm = sum(x * x for x in raw_vector) ** 0.5
        if norm == 0:
            # 극히 드문 전부-0 벡터 케이스를 방지한다.
            raw_vector[0] = 1.0
            norm = 1.0
        return [x / norm for x in raw_vector]


class MockChatCompletionClient:
    """사서 페르소나 고정 문구를 반환하는 Mock 챗 완성 클라이언트."""

    def complete(self, messages: list[dict[str, str]]) -> str:
        last_user_message = next(
            (m["content"] for m in reversed(messages) if m.get("role") == "user"), ""
        )
        book_titles = self._extract_book_titles(last_user_message)
        return _LIBRARIAN_PERSONA_TEMPLATE.format(book_titles=book_titles)

    @staticmethod
    def _extract_book_titles(user_message: str) -> str:
        # Mock 단계에서는 실제 검색 결과를 받지 않으므로 고정 안내 문구를 반환한다.
        # 실제 후보 도서 목록은 ChatService(Task 12)가 조립해 프롬프트에 포함시킨다.
        return "- (검색된 후보 도서 목록은 호출자가 프롬프트에 포함해야 합니다)"
