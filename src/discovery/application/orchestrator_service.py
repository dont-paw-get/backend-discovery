"""오케스트레이터 에이전트와 대화 세션을 조율하는 애플리케이션 서비스.

세션 히스토리를 로드하여 Strands 오케스트레이터 에이전트에 전달하고, 질의 처리 후
사용자 턴과 어시스턴트 턴을 ChatSessionStore에 기록한다.

- 도구 실행 결과(toolResult)는 RecommendBooksTool 내부에서 결정론적으로 권수가 잘린 상태로 반환된다.
- 사서 에이전트 연동 시 세션별 활성 사서 ID와 좌표 정보를 유지하고,
  switch_to 제안을 포착하여 세션을 갱신한다.
"""

import asyncio
import logging
import time
from collections.abc import AsyncGenerator, Callable
from typing import Any

from strands import Agent

from discovery.api.schemas.chat import LibraryBookCard, RecommendedBookCard
from discovery.application.librarian_service import (
    extract_chunk_from_event,
    format_history_for_strands,
)
from discovery.core.cloudwatch_metrics import CloudWatchMetricsPublisher
from discovery.core.config import Settings
from discovery.core.observability import log_agent_metrics
from discovery.core.pricing import estimate_cost_usd
from discovery.domain.librarian.post_processor import (
    extract_text_from_message,
    parse_recommended_books_from_markdown,
    sanitize_html_tags,
)
from discovery.domain.orchestrator.agent import create_orchestrator_agent
from discovery.domain.orchestrator.fallback import get_llm_fallback_message
from discovery.domain.orchestrator.input_gate import evaluate_input_gate
from discovery.domain.orchestrator.librarian_response import (
    LibrarianResponse,
    LibrarianSignals,
    SwitchToSuggestion,
)
from discovery.domain.orchestrator.library_response import LibraryBookItem
from discovery.domain.orchestrator.safety_gate import evaluate_safety_gate
from discovery.domain.orchestrator.tools.librarian_tool import (
    ConsultLibrarianTool,
    evaluate_local_persona_response,
)
from discovery.domain.orchestrator.tools.library_tool import (
    LibraryAuthError,
    SearchMyLibraryTool,
)
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore

logger = logging.getLogger(__name__)

# Bedrock Converse API에서 Claude 도구 호출 포맷 붕괴 시 발생하는 ValidationException 패턴
TOOL_CALL_FORMAT_ERROR_PATTERNS: tuple[str, ...] = (
    "assistant message prefill",
    "must end with a user message",
)


def is_tool_call_format_error(exc: BaseException) -> bool:
    """Bedrock ValidationException 중 assistant prefill 에러인지 판별한다.

    Claude Sonnet 5가 도구 호출 시 toolUse 블록 대신 raw XML 태그를 assistant 텍스트로
    출력했을 때, Strands가 이를 일반 텍스트로 처리하여 다음 Converse 호출 시 대화가
    assistant 턴으로 끝나 Bedrock이 'assistant message prefill' 예외를 반환한다.
    """
    msg = str(exc).lower()
    if any(p in msg for p in TOOL_CALL_FORMAT_ERROR_PATTERNS):
        return True

    if exc.__cause__ is not None and any(
        p in str(exc.__cause__).lower() for p in TOOL_CALL_FORMAT_ERROR_PATTERNS
    ):
        return True
    if exc.__context__ is not None and any(
        p in str(exc.__context__).lower() for p in TOOL_CALL_FORMAT_ERROR_PATTERNS
    ):
        return True

    return False


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


def _build_recommended_book_cards(response_text: str) -> list[RecommendedBookCard] | None:
    """최종 응답 텍스트에서 `### 📖` 도서 블록을 파싱하여 구조화 카드 목록으로 변환한다.

    파싱 결과가 없으면(도서 추천 응답이 아니었거나 파싱 실패) `None`을 반환한다.
    페이지수는 이미 `RecommendBooksTool.recommend()` 단계에서 알라딘 실조회로 검증되어
    마크다운에 반영된 상태이므로(CLIAR-237), 이 함수는 순수하게 파싱만 수행한다.
    """
    parsed = parse_recommended_books_from_markdown(response_text)
    if not parsed:
        return None
    return [
        RecommendedBookCard(
            title=b["title"],
            author=b["author"],
            page_count=b["page_count"],
            reason=b["reason"],
            genre=b["genre"],
        )
        for b in parsed
    ]


async def _publish_cloudwatch_usage_metrics(
    publisher: CloudWatchMetricsPublisher | None,
    model_id: str,
    metrics_summary: dict[str, Any] | None,
) -> None:
    """CLIAR-276: 요청 1건의 토큰 사용량을 CloudWatch에 발행한다.

    기존 `log_agent_metrics`(구조화 로그) 호출과 완전히 독립적으로 동작한다 — 이 함수가
    실패해도 로그·응답 흐름에 영향을 주지 않는다(예외를 삼킨다). `publisher`가 `None`이거나
    비활성(`enabled=False`)이면 즉시 반환한다(플래그 OFF 시 코드 경로 미실행).

    직접 `await`한다 — 내부 `publish_usage`는 `asyncio.to_thread`로 이미 별도 스레드에서
    동작하므로 이벤트 루프를 블로킹하지 않는다. 이전에는 `asyncio.create_task`로
    fire-and-forget 처리했으나, FastAPI 요청 처리 코루틴이 응답을 반환한 직후 종료되면서
    던져둔 태스크가 실행 기회를 얻지 못하고 조용히 소실되는 문제가 dev 실측(2026-09-04)으로
    확인되어 직접 대기 방식으로 전환했다.
    """
    if publisher is None or metrics_summary is None:
        return
    usage = metrics_summary.get("accumulated_usage")
    if not isinstance(usage, dict):
        return

    input_tokens = int(usage.get("inputTokens", 0) or 0)
    output_tokens = int(usage.get("outputTokens", 0) or 0)
    cache_read_tokens = int(usage.get("cacheReadInputTokens", 0) or 0)
    cache_write_tokens = int(usage.get("cacheWriteInputTokens", 0) or 0)
    cost_usd = estimate_cost_usd(model_id, usage)

    try:
        await publisher.publish_usage(
            model_id=model_id,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cache_read_tokens=cache_read_tokens,
            cache_write_tokens=cache_write_tokens,
        )
        logger.info(
            "[CLOUDWATCH_METRICS] Published usage metrics (model=%s, input=%d, output=%d)",
            model_id,
            input_tokens,
            output_tokens,
        )
    except Exception:
        logger.warning("[CLOUDWATCH_METRICS] Failed to publish usage metrics", exc_info=True)


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
        cloudwatch_publisher: CloudWatchMetricsPublisher | None = None,
        boto_session: Any = None,
    ) -> None:
        self._session_store = session_store
        self._settings = settings
        self._recommend_tool = recommend_tool
        self._librarian_tool = librarian_tool
        self._library_tool = library_tool
        self._tools = tools or []
        self._cloudwatch_publisher = cloudwatch_publisher
        self._boto_session = boto_session

    def _build_agent(
        self,
        history: list[dict[str, str]],
        session_id: str,
        meta: dict[str, Any],
        on_librarian_response: Callable[[LibrarianResponse], None] | None = None,
        on_library_books: Callable[[list[LibraryBookItem]], None] | None = None,
        auth_token: str | None = None,
        prefetched_librarian: LibrarianResponse | None = None,
        on_auth_failed: Callable[[], None] | None = None,
    ) -> Agent:
        strands_messages = format_history_for_strands(history)
        librarian_id = meta.get("librarian_id") or "cat"

        active_tools: list[Any] = []
        if self._recommend_tool is not None:
            active_tools.append(
                self._recommend_tool.as_tool(
                    librarian_id=librarian_id,
                    session_id=session_id,
                    auth_token=auth_token,
                )
            )
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
                    prefetched=prefetched_librarian,
                )
            )
        if self._library_tool is not None:
            active_tools.append(
                self._library_tool.as_tool(
                    auth_token=auth_token,
                    on_books_fetched=on_library_books,
                    on_auth_failed=on_auth_failed,
                )
            )

        if not active_tools and self._tools:
            active_tools = self._tools

        return create_orchestrator_agent(
            model_id=self._settings.orchestrator_model_id,
            region_name=self._settings.aws_region,
            boto_session=self._boto_session,
            librarian_id=librarian_id,
            tools=active_tools,
            messages=strands_messages if strands_messages else None,
            enable_prompt_caching=self._settings.enable_prompt_caching,
        )

    async def chat(
        self,
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        auth_token: str | None = None,
    ) -> tuple[
        str,
        SwitchToSuggestion | None,
        LibrarianSignals | None,
        list[LibraryBookCard] | None,
        list[RecommendedBookCard] | None,
    ]:
        """단일 턴 동기 대화 응답을 생성하고 세션 히스토리 및 메타를 갱신한다."""
        start_time = time.perf_counter()
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

        # Task 3: 위기/자해 대응 안전 게이트 (결정론적 우회)
        safety_response = evaluate_safety_gate(message, meta.get("librarian_id"))
        if safety_response is not None:
            await self._session_store.append_turn(session_id, {"role": "user", "content": message})
            await self._session_store.append_turn(
                session_id, {"role": "assistant", "content": safety_response}
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_agent_metrics(
                phase="orchestrator",
                session_id=session_id,
                librarian_id=meta.get("librarian_id"),
                mode="sync",
                message_length=len(message),
                metrics_summary=None,
                direct_metrics={"total_duration_ms": duration_ms, "safety_gate_triggered": True},
            )
            return safety_response, None, None, None, None

        # Task 4: 비정상 입력 게이트 (자모/숫자/이모지 결정론적 우회)
        input_gate_response = evaluate_input_gate(message, meta.get("librarian_id"))
        if input_gate_response is not None:
            await self._session_store.append_turn(session_id, {"role": "user", "content": message})
            await self._session_store.append_turn(
                session_id, {"role": "assistant", "content": input_gate_response}
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_agent_metrics(
                phase="orchestrator",
                session_id=session_id,
                librarian_id=meta.get("librarian_id"),
                mode="sync",
                message_length=len(message),
                metrics_summary=None,
                direct_metrics={"total_duration_ms": duration_ms, "input_gate_triggered": True},
            )
            return input_gate_response, None, None, None, None

        switch_to_holder: list[SwitchToSuggestion] = []
        signals_holder: list[LibrarianSignals] = []
        library_books_holder: list[LibraryBookCard] = []
        consult_called = False
        auth_failed = False

        def on_librarian_response(res: LibrarianResponse) -> None:
            nonlocal consult_called
            consult_called = True
            if res.signals is not None:
                signals_holder.append(res.signals)
            if res.switch_to is not None and not switch_to_holder:
                switch_to_holder.append(res.switch_to)

        def on_library_books(books: list[LibraryBookItem]) -> None:
            cards = [
                LibraryBookCard(
                    book_id=b.book_id,
                    title=b.title,
                    author=b.author,
                    reading_status=b.reading_status,
                    progress=b.progress,
                )
                for b in books
            ]
            library_books_holder.clear()
            library_books_holder.extend(cards)

        def on_auth_failed() -> None:
            nonlocal auth_failed
            auth_failed = True

        agent = self._build_agent(
            history=history,
            session_id=session_id,
            meta=meta,
            on_librarian_response=on_librarian_response,
            on_library_books=on_library_books,
            auth_token=auth_token,
            on_auth_failed=on_auth_failed,
        )

        orchestrator_metrics: dict[str, Any] | None = None
        format_retry_triggered = False
        try:
            result = await agent.invoke_async(prompt=message)
        except Exception as e:
            if is_tool_call_format_error(e):
                format_retry_triggered = True
                logger.warning(
                    "[FORMAT_COLLAPSE_RETRY] Detected assistant prefill format collapse in chat. "
                    "Rebuilding agent and retrying 1 time (session_id=%s, librarian_id=%s): %s",
                    session_id,
                    meta.get("librarian_id"),
                    e,
                )
                switch_to_holder.clear()
                signals_holder.clear()
                library_books_holder.clear()
                consult_called = False
                auth_failed = False

                agent = self._build_agent(
                    history=history,
                    session_id=session_id,
                    meta=meta,
                    on_librarian_response=on_librarian_response,
                    on_library_books=on_library_books,
                    auth_token=auth_token,
                    on_auth_failed=on_auth_failed,
                )
                try:
                    result = await agent.invoke_async(prompt=message)
                except Exception as retry_err:
                    logger.exception(
                        "[BEDROCK_FALLBACK] chat retry also failed "
                        "(session_id=%s, librarian_id=%s): %s",
                        session_id,
                        meta.get("librarian_id"),
                        retry_err,
                    )
                    result = None
                    response_text = get_llm_fallback_message(meta.get("librarian_id"))
            else:
                logger.exception(
                    "[BEDROCK_FALLBACK] chat invoke failed (session_id=%s, librarian_id=%s): %s",
                    session_id,
                    meta.get("librarian_id"),
                    e,
                )
                result = None
                response_text = get_llm_fallback_message(meta.get("librarian_id"))

        if result is not None:
            if hasattr(result, "metrics") and result.metrics:
                orchestrator_metrics = result.metrics.get_summary()
            response_text = extract_text_from_message(result.message)
            tool_result = extract_fallback_text(agent)

            if tool_result:
                has_rec_card = "### 📖" in tool_result
                has_lib_card = "### 📚" in tool_result
                missing_rec = has_rec_card and "### 📖" not in response_text
                missing_lib = has_lib_card and "### 📚" not in response_text

                if (missing_rec or missing_lib) and tool_result not in response_text:
                    if response_text.strip():
                        response_text = f"{response_text.strip()}\n\n{tool_result}"
                    else:
                        response_text = tool_result
                elif not response_text.strip():
                    response_text = tool_result

        # ADR 0007 2.2절: backend-book이 401(위조/만료 토큰)을 반환하면 조용히
        # 흡수하지 않고 라우터가 401로 전달할 수 있도록 예외를 다시 던진다.
        # (도구 실행 결과에 이미 안전한 문구가 담겨 있으므로 LLM 흐름 자체는 깨지지 않았다.)
        if auth_failed:
            raise LibraryAuthError("Library API authentication failed")

        # Task 2-1: 도구가 consult를 한 번도 호출하지 않았을 때만(예: 순수 서재 조회 등)
        # 잔여 호출 수행 (동기 경로는 기본 HTTP 타임아웃 유지)
        if not consult_called and self._librarian_tool is not None:
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
                if lib_res.switch_to is not None and not switch_to_holder:
                    switch_to_holder.append(lib_res.switch_to)
            except Exception as e:
                logger.warning("[BEDROCK_FALLBACK] librarian fallback consult failed: %s", e)

        if not signals_holder:
            local_res = evaluate_local_persona_response(
                message=message,
                librarian_id=meta.get("librarian_id"),
                latitude=meta.get("latitude"),
                longitude=meta.get("longitude"),
            )
            if local_res.signals is not None:
                signals_holder.append(local_res.signals)

        switch_to: SwitchToSuggestion | None = switch_to_holder[0] if switch_to_holder else None
        signals: LibrarianSignals | None = signals_holder[0] if signals_holder else None
        if switch_to is not None:
            await self._session_store.update_session_meta(session_id, librarian_id=switch_to.id)

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": response_text}
        )
        library_books: list[LibraryBookCard] | None = (
            list(library_books_holder) if library_books_holder else None
        )
        response_text = sanitize_html_tags(response_text)
        recommended_books = _build_recommended_book_cards(response_text)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        direct_metrics: dict[str, Any] = {"total_duration_ms": duration_ms}
        if format_retry_triggered:
            direct_metrics["format_retry_triggered"] = True
        log_agent_metrics(
            phase="orchestrator",
            session_id=session_id,
            librarian_id=meta.get("librarian_id"),
            mode="sync",
            message_length=len(message),
            metrics_summary=orchestrator_metrics,
            direct_metrics=direct_metrics,
        )
        await _publish_cloudwatch_usage_metrics(
            self._cloudwatch_publisher, self._settings.orchestrator_model_id, orchestrator_metrics
        )
        return response_text, switch_to, signals, library_books, recommended_books

    async def get_initial_meta(
        self,
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
    ) -> LibrarianResponse | None:
        """스트리밍 응답 헤더(X-Signals, X-Switch-To)에 실어줄 사서 신호와
        스위칭 제안 및 첫 턴 도구 실행 시 재사용할 사전 메타 응답을 조회한다.

        사서 서버 지연으로 인한 전체 스트리밍 블로킹을 방지하기 위해
        initial_meta_timeout_seconds(기본 1.5초) Fail-Fast 타임아웃을 적용한다.
        """
        init_start = time.perf_counter()
        if librarian_id is not None:
            await self._session_store.update_session_meta(session_id, librarian_id=librarian_id)

        lib_res: LibrarianResponse | None = None
        if self._librarian_tool is not None:
            timeout_sec = self._settings.initial_meta_timeout_seconds
            try:
                meta = await self._session_store.get_session_meta(session_id)
                lib_res = await asyncio.wait_for(
                    self._librarian_tool.consult(
                        message=message,
                        session_id=session_id,
                        librarian_id=meta.get("librarian_id"),
                        latitude=latitude or meta.get("latitude"),
                        longitude=longitude or meta.get("longitude"),
                    ),
                    timeout=timeout_sec,
                )
            except TimeoutError:
                logger.warning(
                    "[INITIAL_META_TIMEOUT] get_initial_meta timed out (%.1fs, session_id=%s). "
                    "Bypassing to fast stream.",
                    timeout_sec,
                    session_id,
                )
            except Exception as e:
                logger.warning("[INITIAL_META_FALLBACK] get_initial_meta failed: %s", e)

        init_duration_ms = round((time.perf_counter() - init_start) * 1000, 2)
        log_agent_metrics(
            phase="initial_meta",
            session_id=session_id,
            librarian_id=librarian_id or "cat",
            mode="sync",
            message_length=len(message),
            direct_metrics={"initial_meta_ms": init_duration_ms},
        )
        return lib_res

    async def stream_chat(
        self,
        session_id: str,
        message: str,
        librarian_id: str | None = None,
        latitude: float | None = None,
        longitude: float | None = None,
        auth_token: str | None = None,
        prefetched_librarian: LibrarianResponse | None = None,
    ) -> AsyncGenerator[str, None]:
        """스트리밍 대화 응답을 청크 단위로 yield하고, 완료 후 세션 히스토리를 갱신한다."""
        start_time = time.perf_counter()
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

        # Task 3: 위기/자해 대응 안전 게이트 (결정론적 우회)
        safety_response = evaluate_safety_gate(message, meta.get("librarian_id"))
        if safety_response is not None:
            await self._session_store.append_turn(session_id, {"role": "user", "content": message})
            await self._session_store.append_turn(
                session_id, {"role": "assistant", "content": safety_response}
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_agent_metrics(
                phase="orchestrator",
                session_id=session_id,
                librarian_id=meta.get("librarian_id"),
                mode="stream",
                message_length=len(message),
                metrics_summary=None,
                direct_metrics={
                    "ttfb_ms": duration_ms,
                    "total_duration_ms": duration_ms,
                    "safety_gate_triggered": True,
                },
            )
            yield safety_response
            return

        # Task 4: 비정상 입력 게이트 (자모/숫자/이모지 결정론적 우회)
        input_gate_response = evaluate_input_gate(message, meta.get("librarian_id"))
        if input_gate_response is not None:
            await self._session_store.append_turn(session_id, {"role": "user", "content": message})
            await self._session_store.append_turn(
                session_id, {"role": "assistant", "content": input_gate_response}
            )
            duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
            log_agent_metrics(
                phase="orchestrator",
                session_id=session_id,
                librarian_id=meta.get("librarian_id"),
                mode="stream",
                message_length=len(message),
                metrics_summary=None,
                direct_metrics={
                    "ttfb_ms": duration_ms,
                    "total_duration_ms": duration_ms,
                    "input_gate_triggered": True,
                },
            )
            yield input_gate_response
            return

        switch_to_holder: list[SwitchToSuggestion] = []
        library_books_holder: list[LibraryBookCard] = []
        consult_called = False
        auth_failed = False

        if prefetched_librarian is not None and prefetched_librarian.switch_to is not None:
            switch_to_holder.append(prefetched_librarian.switch_to)

        def on_librarian_response(res: LibrarianResponse) -> None:
            nonlocal consult_called
            consult_called = True
            if res.switch_to is not None and not switch_to_holder:
                switch_to_holder.append(res.switch_to)

        def on_auth_failed() -> None:
            nonlocal auth_failed
            auth_failed = True

        def on_library_books(books: list[LibraryBookItem]) -> None:
            cards = [
                LibraryBookCard(
                    book_id=b.book_id,
                    title=b.title,
                    author=b.author,
                    reading_status=b.reading_status,
                    progress=b.progress,
                )
                for b in books
            ]
            library_books_holder.clear()
            library_books_holder.extend(cards)

        agent = self._build_agent(
            history=history,
            session_id=session_id,
            meta=meta,
            on_librarian_response=on_librarian_response,
            on_library_books=on_library_books,
            auth_token=auth_token,
            prefetched_librarian=prefetched_librarian,
            on_auth_failed=on_auth_failed,
        )

        full_response: list[str] = []
        ttfb_ms: float | None = None
        orchestrator_metrics: dict[str, Any] | None = None
        format_retry_triggered = False

        try:
            async for event in agent.stream_async(prompt=message):
                chunk = extract_chunk_from_event(event)
                if chunk:
                    if ttfb_ms is None:
                        ttfb_ms = round((time.perf_counter() - start_time) * 1000, 2)
                    full_response.append(chunk)
                    yield chunk
                if isinstance(event, dict) and "result" in event:
                    res_obj = event["result"]
                    if hasattr(res_obj, "metrics") and res_obj.metrics:
                        orchestrator_metrics = res_obj.metrics.get_summary()
        except Exception as e:
            if is_tool_call_format_error(e) and not full_response:
                format_retry_triggered = True
                logger.warning(
                    "[FORMAT_COLLAPSE_RETRY] Detected assistant prefill format collapse "
                    "before TTFB in stream. Rebuilding agent and retrying 1 time "
                    "(session_id=%s, librarian_id=%s): %s",
                    session_id,
                    meta.get("librarian_id"),
                    e,
                )
                switch_to_holder.clear()
                library_books_holder.clear()
                consult_called = False
                auth_failed = False
                if prefetched_librarian is not None and prefetched_librarian.switch_to is not None:
                    switch_to_holder.append(prefetched_librarian.switch_to)

                agent = self._build_agent(
                    history=history,
                    session_id=session_id,
                    meta=meta,
                    on_librarian_response=on_librarian_response,
                    on_library_books=on_library_books,
                    auth_token=auth_token,
                    prefetched_librarian=prefetched_librarian,
                    on_auth_failed=on_auth_failed,
                )
                try:
                    async for event in agent.stream_async(prompt=message):
                        chunk = extract_chunk_from_event(event)
                        if chunk:
                            if ttfb_ms is None:
                                ttfb_ms = round((time.perf_counter() - start_time) * 1000, 2)
                            full_response.append(chunk)
                            yield chunk
                        if isinstance(event, dict) and "result" in event:
                            res_obj = event["result"]
                            if hasattr(res_obj, "metrics") and res_obj.metrics:
                                orchestrator_metrics = res_obj.metrics.get_summary()
                except Exception as retry_err:
                    logger.exception(
                        "[BEDROCK_FALLBACK] stream_chat retry also failed "
                        "(session_id=%s, librarian_id=%s): %s",
                        session_id,
                        meta.get("librarian_id"),
                        retry_err,
                    )
                    fallback_chunk = get_llm_fallback_message(meta.get("librarian_id"))
                    if full_response:
                        fallback_chunk = f"\n\n{fallback_chunk}"
                    full_response.append(fallback_chunk)
                    yield fallback_chunk
            else:
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

        # ADR 0007 2.2절: backend-book이 401(위조/만료 토큰)을 반환하면 동기(chat)
        # 경로는 예외로 전달해 라우터가 401을 반환할 수 있게 한다. 스트리밍 경로는
        # StreamingResponse가 200 헤더를 먼저 확정하므로 상태 코드 전달이 구조적으로
        # 불가능하다 — 도구가 반환한 안내 문구가 본문에 자연스럽게 포함되도록 둔다
        # (auth_failed 플래그를 raise하지 않고 로그만 남긴다).
        if auth_failed:
            logger.warning(
                "[LIBRARY_AUTH_FAILED] stream_chat cannot propagate 401 after headers sent "
                "(session_id=%s)",
                session_id,
            )

        response_text = "".join(full_response)
        tool_result = extract_fallback_text(agent)

        if tool_result:
            has_rec_card = "### 📖" in tool_result
            has_lib_card = "### 📚" in tool_result
            missing_rec = has_rec_card and "### 📖" not in response_text
            missing_lib = has_lib_card and "### 📚" not in response_text

            if (missing_rec or missing_lib) and tool_result not in response_text:
                append_chunk = f"\n\n{tool_result}" if response_text.strip() else tool_result
                yield append_chunk
                if response_text.strip():
                    response_text = f"{response_text.strip()}\n\n{tool_result}"
                else:
                    response_text = tool_result
            elif not response_text.strip():
                yield tool_result
                response_text = tool_result

        # Task 2-1: 도구가 consult를 호출하지 않았고 prefetched도 없었을 때만
        # tail consult 수행 + 1.5초 타임아웃 가드
        if (
            not consult_called
            and prefetched_librarian is None
            and self._librarian_tool is not None
        ):
            timeout_sec = self._settings.initial_meta_timeout_seconds
            try:
                lib_res = await asyncio.wait_for(
                    self._librarian_tool.consult(
                        message=message,
                        session_id=session_id,
                        librarian_id=meta.get("librarian_id"),
                        latitude=meta.get("latitude"),
                        longitude=meta.get("longitude"),
                    ),
                    timeout=timeout_sec,
                )
                if lib_res.switch_to is not None and not switch_to_holder:
                    switch_to_holder.append(lib_res.switch_to)
            except Exception as e:
                logger.warning("[BEDROCK_FALLBACK] librarian stream tail consult failed: %s", e)

        if switch_to_holder:
            await self._session_store.update_session_meta(
                session_id, librarian_id=switch_to_holder[0].id
            )

        await self._session_store.append_turn(session_id, {"role": "user", "content": message})
        await self._session_store.append_turn(
            session_id, {"role": "assistant", "content": sanitize_html_tags(response_text)}
        )

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        direct_metrics_stream: dict[str, Any] = {
            "ttfb_ms": ttfb_ms,
            "total_duration_ms": duration_ms,
        }
        if format_retry_triggered:
            direct_metrics_stream["format_retry_triggered"] = True
        log_agent_metrics(
            phase="orchestrator",
            session_id=session_id,
            librarian_id=meta.get("librarian_id"),
            mode="stream",
            message_length=len(message),
            metrics_summary=orchestrator_metrics,
            direct_metrics=direct_metrics_stream,
        )
        await _publish_cloudwatch_usage_metrics(
            self._cloudwatch_publisher, self._settings.orchestrator_model_id, orchestrator_metrics
        )


