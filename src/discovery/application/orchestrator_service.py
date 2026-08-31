"""오케스트레이터 에이전트와 대화 세션을 조율하는 애플리케이션 서비스.

세션 히스토리를 로드하여 Strands 오케스트레이터 에이전트에 전달하고, 질의 처리 후
사용자 턴과 어시스턴트 턴을 ChatSessionStore에 기록한다.

- 도구 실행 결과(toolResult)는 RecommendBooksTool 내부에서 결정론적으로 권수가 잘린 상태로 반환된다.
- 사서 에이전트 연동 시 세션별 활성 사서 ID와 좌표 정보를 유지하고,
  switch_to 제안을 포착하여 세션을 갱신한다.
"""

import logging
from collections.abc import AsyncGenerator
from typing import Any

from strands import Agent

from discovery.application.librarian_service import (
    extract_chunk_from_event,
    format_history_for_strands,
)
from discovery.core.config import Settings
from discovery.domain.librarian.post_processor import extract_text_from_message
from discovery.domain.orchestrator.agent import create_orchestrator_agent
from discovery.domain.orchestrator.fallback import get_llm_fallback_message
from discovery.domain.orchestrator.librarian_response import (
    LibrarianResponse,
    LibrarianSignals,
    SwitchToSuggestion,
)
from discovery.domain.orchestrator.tools.librarian_tool import ConsultLibrarianTool
from discovery.domain.orchestrator.tools.library_tool import SearchMyLibraryTool
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore

logger = logging.getLogger(__name__)


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
        recommend_tool: RecommendBooksTool | None = None,
        librarian_tool: ConsultLibrarianTool | None = None,
        library_tool: SearchMyLibraryTool | None = None,
        tools: list[Any] | None = None,
    ) -> None:
        self._session_store = session_store
        self._settings = settings
        self._recommend_tool = recommend_tool
        self._librarian_tool = librarian_tool
        self._library_tool = library_tool
        self._tools = tools or []

    def _build_agent(
        self,
        history: list[dict[str, str]],
        session_id: str,
        meta: dict[str, Any],
        on_librarian_response: Any = None,
        auth_token: str | None = None,
    ) -> Agent:
        strands_messages = format_history_for_strands(history)
        librarian_id = meta.get("librarian_id") or "cat"

        active_tools: list[Any] = []
        if self._recommend_tool is not None:
            active_tools.append(self._recommend_tool.as_tool(librarian_id=librarian_id))
        if self._librarian_tool is not None:
            latitude = meta.get("latitude")
            longitude = meta.get("longitude")
            active_tools.append(
                self._librarian_tool.as_tool(
                    session_id=session_id,
                    librarian_id=librarian_id,
                    latitude=latitude,
                    longitude=longitude,
                    on_response=on_librarian_response,
                )
            )
        if self._library_tool is not None:
            active_tools.append(self._library_tool.as_tool(auth_token=auth_token))

        if not active_tools and self._tools:
            active_tools = self._tools

        return create_orchestrator_agent(
            model_id=self._settings.orchestrator_model_id,
            region_name=self._settings.aws_region,
            librarian_id=librarian_id,
            tools=active_tools,
            messages=strands_messages if strands_messages else None,
        )

    async def chat(
        self,
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        auth_token: str | None = None,
    ) -> tuple[str, SwitchToSuggestion | None, LibrarianSignals | None]:
        """단일 턴 동기 대화 응답을 생성하고 세션 히스토리 및 메타를 갱신한다."""
        meta_updates: dict[str, Any] = {}
        if librarian_id is not None:
            meta_updates["librarian_id"] = librarian_id
        if latitude is not None:
            meta_updates["latitude"] = latitude
        if longitude is not None:
            meta_updates["longitude"] = longitude

        if meta_updates:
            await self._session_store.update_session_meta(session_id, **meta_updates)

        meta = await self._session_store.get_session_meta(session_id)
        history = await self._session_store.get_history(session_id)

        switch_to_holder: list[SwitchToSuggestion] = []
        signals_holder: list[LibrarianSignals] = []

        def on_librarian_response(res: LibrarianResponse) -> None:
            if res.signals is not None:
                signals_holder.append(res.signals)
            if res.switch_to is not None:
                switch_to_holder.append(res.switch_to)

        agent = self._build_agent(
            history=history,
            session_id=session_id,
            meta=meta,
            on_librarian_response=on_librarian_response,
            auth_token=auth_token,
        )

        try:
            result = await agent.invoke_async(prompt=message)
            response_text = extract_text_from_message(result.message)
            tool_result = extract_fallback_text(agent)

            if tool_result:
                has_book_card = "### 📖" in tool_result
                if has_book_card and "### 📖" not in response_text:
                    if response_text.strip():
                        response_text = f"{response_text.strip()}\n\n{tool_result}"
                    else:
                        response_text = tool_result
                elif not response_text.strip():
                    response_text = tool_result
        except Exception as e:
            logger.exception(
                "[BEDROCK_FALLBACK] chat invoke failed (session_id=%s, librarian_id=%s): %s",
                session_id,
                meta.get("librarian_id"),
                e,
            )
            response_text = get_llm_fallback_message(meta.get("librarian_id"))

        if not switch_to_holder and self._librarian_tool is not None:
            try:
                lib_res = await self._librarian_tool.consult(
                    message=message,
                    session_id=session_id,
                    librarian_id=meta.get("librarian_id"),
                    latitude=meta.get("latitude"),
                    longitude=meta.get("longitude"),
                )
                if lib_res.signals is not None and not signals_holder:
                    signals_holder.append(lib_res.signals)
                if lib_res.switch_to is not None:
                    switch_to_holder.append(lib_res.switch_to)
            except Exception as e:
                logger.warning("[BEDROCK_FALLBACK] librarian fallback consult failed: %s", e)

        switch_to: SwitchToSuggestion | None = switch_to_holder[0] if switch_to_holder else None
        signals: LibrarianSignals | None = signals_holder[0] if signals_holder else None
        if switch_to is not None:
            await self._session_store.update_session_meta(session_id, librarian_id=switch_to.id)

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
        return response_text, switch_to, signals

    async def get_initial_meta(
        self,
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> tuple[LibrarianSignals | None, SwitchToSuggestion | None]:
        """스트리밍 응답 헤더(X-Signals, X-Switch-To)에 실어줄 사서 신호와
        스위칭 제안을 사전 계산한다."""
        if librarian_id is not None:
            await self._session_store.update_session_meta(session_id, librarian_id=librarian_id)

        if self._librarian_tool is not None:
            try:
                meta = await self._session_store.get_session_meta(session_id)
                lib_res = await self._librarian_tool.consult(
                    message=message,
                    session_id=session_id,
                    librarian_id=meta.get("librarian_id"),
                    latitude=latitude or meta.get("latitude"),
                    longitude=longitude or meta.get("longitude"),
                )
                return lib_res.signals, lib_res.switch_to
            except Exception as e:
                logger.warning("[BEDROCK_FALLBACK] get_initial_meta failed: %s", e)
                return None, None
        return None, None

    async def stream_chat(
        self,
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        auth_token: str | None = None,
    ) -> AsyncGenerator[str, None]:
        """스트리밍 대화 응답을 청크 단위로 yield하고, 완료 후 세션 히스토리를 갱신한다."""
        meta_updates: dict[str, Any] = {}
        if librarian_id is not None:
            meta_updates["librarian_id"] = librarian_id
        if latitude is not None:
            meta_updates["latitude"] = latitude
        if longitude is not None:
            meta_updates["longitude"] = longitude

        if meta_updates:
            await self._session_store.update_session_meta(session_id, **meta_updates)

        meta = await self._session_store.get_session_meta(session_id)
        history = await self._session_store.get_history(session_id)

        switch_to_holder: list[SwitchToSuggestion] = []

        def on_librarian_response(res: LibrarianResponse) -> None:
            if res.switch_to is not None:
                switch_to_holder.append(res.switch_to)

        agent = self._build_agent(
            history=history,
            session_id=session_id,
            meta=meta,
            on_librarian_response=on_librarian_response,
            auth_token=auth_token,
        )

        full_response: list[str] = []
        try:
            async for event in agent.stream_async(prompt=message):
                chunk = extract_chunk_from_event(event)
                if chunk:
                    full_response.append(chunk)
                    yield chunk
        except Exception as e:
            logger.exception(
                "[BEDROCK_FALLBACK] stream_chat failed (session_id=%s, librarian_id=%s): %s",
                session_id,
                meta.get("librarian_id"),
                e,
            )
            fallback_chunk = get_llm_fallback_message(meta.get("librarian_id"))
            if full_response:
                fallback_chunk = f"\n\n{fallback_chunk}"
            full_response.append(fallback_chunk)
            yield fallback_chunk

        response_text = "".join(full_response)
        tool_result = extract_fallback_text(agent)

        if tool_result:
            has_book_card = "### 📖" in tool_result
            if has_book_card and "### 📖" not in response_text:
                append_chunk = f"\n\n{tool_result}" if response_text.strip() else tool_result
                yield append_chunk
                if response_text.strip():
                    response_text = f"{response_text.strip()}\n\n{tool_result}"
                else:
                    response_text = tool_result
            elif not response_text.strip():
                yield tool_result
                response_text = tool_result

        if not switch_to_holder and self._librarian_tool is not None:
            lib_res = await self._librarian_tool.consult(
                message=message,
                session_id=session_id,
                librarian_id=meta.get("librarian_id"),
                latitude=meta.get("latitude"),
                longitude=meta.get("longitude"),
            )
            if lib_res.switch_to is not None:
                switch_to_holder.append(lib_res.switch_to)

        if switch_to_holder:
            await self._session_store.update_session_meta(
                session_id, librarian_id=switch_to_holder[0].id
            )

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )

