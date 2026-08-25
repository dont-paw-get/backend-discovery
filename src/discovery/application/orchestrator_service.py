"""오케스트레이터 에이전트와 대화 세션을 조율하는 애플리케이션 서비스.

세션 히스토리를 로드하여 Strands 오케스트레이터 에이전트에 전달하고, 질의 처리 후
사용자 턴과 어시스턴트 턴을 ChatSessionStore에 기록한다.

- 도구 실행 결과(toolResult)는 RecommendBooksTool 내부에서 결정론적으로 권수가 잘린 상태로 반환된다.
- 향후 과제(직결 스트리밍 파이프라인): 오케스트레이터의 2차 생성 지연을 줄이기 위해
  하위 추천 에이전트의 토큰 스트림을 직접 클라이언트로 중계하며, N+1번째 `### 📖` 감지 시
  조기 중단(Early Stop)하는 증분 방식으로 전환한다.
"""

from collections.abc import AsyncGenerator
from typing import Any

from strands import Agent

from discovery.application.librarian_service import (
    extract_chunk_from_event,
    extract_text_from_message,
    format_history_for_strands,
)
from discovery.core.config import Settings
from discovery.domain.orchestrator.agent import create_orchestrator_agent
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore


def extract_fallback_text(agent: Agent) -> str:
    """오케스트레이터가 도구 실행 후 텍스트를 생성하지 않았을 때 toolResult 텍스트를 추출한다."""
    messages = getattr(agent, "messages", [])
    if not isinstance(messages, list):
        return ""

    for msg in reversed(messages):
        if not isinstance(msg, dict):
            continue
        content = msg.get("content", [])
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if "toolResult" in block and isinstance(block["toolResult"], dict):
                tr_content = block["toolResult"].get("content", [])
                if isinstance(tr_content, list):
                    texts = [
                        item.get("text", "")
                        for item in tr_content
                        if isinstance(item, dict)
                        and "text" in item
                        and isinstance(item["text"], str)
                    ]
                    combined = "".join(texts).strip()
                    if combined:
                        return combined
                elif isinstance(tr_content, str) and tr_content.strip():
                    return tr_content.strip()
    return ""


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
        tool_result = extract_fallback_text(agent)

        if tool_result and "### 📖" not in response_text:
            if response_text.strip():
                response_text = f"{response_text.strip()}\n\n{tool_result}"
            else:
                response_text = tool_result
        elif not response_text.strip() and tool_result:
            response_text = tool_result

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
        return response_text

    async def stream_chat(self, session_id: str, message: str) -> AsyncGenerator[str, None]:
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
        tool_result = extract_fallback_text(agent)

        if tool_result and "### 📖" not in response_text:
            append_chunk = f"\n\n{tool_result}" if response_text.strip() else tool_result
            yield append_chunk
            if response_text.strip():
                response_text = f"{response_text.strip()}\n\n{tool_result}"
            else:
                response_text = tool_result
        elif not response_text.strip() and tool_result:
            yield tool_result
            response_text = tool_result

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
