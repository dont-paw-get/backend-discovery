"""오케스트레이터 에이전트와 대화 세션을 조율하는 애플리케이션 서비스.

세션 히스토리를 로드하여 Strands 오케스트레이터 에이전트에 전달하고, 질의 처리 후
사용자 턴과 어시스턴트 턴을 ChatSessionStore에 기록한다.
"""

from collections.abc import AsyncGenerator
from typing import Any

from strands import Agent

from discovery.application.librarian_service import (
    extract_text_from_message,
    format_history_for_strands,
)
from discovery.core.config import Settings
from discovery.domain.orchestrator.agent import create_orchestrator_agent
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore


class OrchestratorService:
    """오케스트레이터 에이전트 대화 및 세션 관리를 총괄하는 서비스."""

    def __init__(
        self,
        session_store: ChatSessionStore,
        settings: Settings,
        tools: list[Any] | None = None,
    ) -> None:
        self._session_store = session_store
        self._settings = settings
        self._tools = tools or []

    def _build_agent(self, history: list[dict[str, str]]) -> Agent:
        strands_messages = format_history_for_strands(history)
        return create_orchestrator_agent(
            model_id=self._settings.orchestrator_model_id,
            region_name=self._settings.aws_region,
            tools=self._tools,
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
            if isinstance(event, dict) and "data" in event and isinstance(event["data"], str):
                chunk = event["data"]
                if chunk:
                    full_response.append(chunk)
                    yield chunk

        response_text = "".join(full_response)
        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
