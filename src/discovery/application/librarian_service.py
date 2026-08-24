"""추천 에이전트와 대화 세션을 조율하는 애플리케이션 서비스.

세션 히스토리를 로드하여 Strands 에이전트에 전달하고, 질의 처리 후 사용자 턴과
어시스턴트 턴을 ChatSessionStore에 기록한다.
"""

from collections.abc import AsyncGenerator
from typing import Any

from strands import Agent

from discovery.core.config import Settings
from discovery.domain.librarian.agent import create_librarian_agent
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore
from discovery.infrastructure.search.book_search_tool import BookSearchTool


def format_history_for_strands(history: list[dict[str, str]]) -> list[dict[str, Any]]:
    """ChatSessionStore의 히스토리를 Strands Agent가 인식할 수 있는 Message 구조로 변환한다."""
    return [{"role": turn["role"], "content": [{"text": turn["content"]}]} for turn in history]


def extract_text_from_message(message: Any) -> str:
    """AgentResult.message에서 텍스트 콘텐츠를 추출한다."""
    if isinstance(message, dict):
        content = message.get("content", [])
        if isinstance(content, list):
            return "".join(
                b.get("text", "")
                for b in content
                if isinstance(b, dict) and "text" in b and isinstance(b["text"], str)
            )
    return ""


def extract_chunk_from_event(event: Any) -> str:
    """Strands stream 이벤트에서 텍스트 청크를 안전하게 추출한다."""
    if not isinstance(event, dict):
        return ""

    # 1. TextStreamEvent: {"data": "..."}
    if "data" in event and isinstance(event["data"], str):
        return event["data"]

    # 2. contentBlockDelta: {"contentBlockDelta": {"delta": {"text": "..."}}}
    if "contentBlockDelta" in event and isinstance(event["contentBlockDelta"], dict):
        delta = event["contentBlockDelta"].get("delta", {})
        if isinstance(delta, dict) and "text" in delta and isinstance(delta["text"], str):
            return delta["text"]

    # 3. delta text: {"delta": {"text": "..."}}
    if "delta" in event and isinstance(event["delta"], dict):
        text = event["delta"].get("text")
        if isinstance(text, str):
            return text

    return ""


class LibrarianService:
    """추천 에이전트 대화 및 세션 관리를 총괄하는 서비스."""

    def __init__(
        self,
        session_store: ChatSessionStore,
        book_search_tool: BookSearchTool,
        settings: Settings,
    ) -> None:
        self._session_store = session_store
        self._book_search_tool = book_search_tool
        self._settings = settings

    def _build_agent(self, history: list[dict[str, str]]) -> Agent:
        strands_messages = format_history_for_strands(history)
        tools = [self._book_search_tool.as_tool()]
        return create_librarian_agent(
            model_id=self._settings.librarian_model_id,
            region_name=self._settings.aws_region,
            tools=tools,
            messages=strands_messages if strands_messages else None,
        )

    async def chat(self, session_id: str, message: str) -> str:
        """단일 턴 동기 대화 응답을 생성하고 세션 히스토리를 갱신한다."""
        history = await self._session_store.get_history(session_id)
        agent = self._build_agent(history)

        result = await agent.invoke_async(prompt=message)
        response_text = extract_text_from_message(result.message)

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
        return response_text

    async def stream_chat(
        self, session_id: str, message: str
    ) -> AsyncGenerator[str, None]:
        """스트리밍 대화 응답을 청크 단위로 yield하고, 완료 후 세션 히스토리를 갱신한다."""
        history = await self._session_store.get_history(session_id)
        agent = self._build_agent(history)

        full_response: list[str] = []
        async for event in agent.stream_async(prompt=message):
            chunk = extract_chunk_from_event(event)
            if chunk:
                full_response.append(chunk)
                yield chunk

        response_text = "".join(full_response)
        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
