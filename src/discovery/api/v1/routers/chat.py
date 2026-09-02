"""오케스트레이터 대화 API 라우터."""

import urllib.parse
import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse

from discovery.api.deps import get_orchestrator_service, require_authorization_header
from discovery.api.schemas.chat import ChatRequest, ChatResponse
from discovery.application.orchestrator_service import OrchestratorService
from discovery.domain.orchestrator.tools.librarian_tool import evaluate_local_persona_response
from discovery.domain.orchestrator.tools.library_tool import LibraryAuthError

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        200: {
            "description": "오케스트레이터 답변 (일반 JSON 또는 stream=True 시 스트리밍 텍스트)",
            "content": {
                "application/json": {},
                "text/plain": {},
            },
        },
        401: {
            "description": (
                "인증 실패 (Authorization 헤더 누락/빈 값, "
                "또는 서재 API가 위조·만료된 토큰으로 인증 실패를 반환한 경우)"
            ),
        },
    },
    summary="오케스트레이터 대화 (도서 추천, 서재 검색, 사서 상담)",
    description=(
        "자연어 질문으로 오케스트레이터에게 대화를 요청한다. "
        "의도에 따라 내 서재 도서 검색, 외부 도서 추천 또는 사서 에이전트로 라우팅되며, "
        "이전 세션 ID를 전달하면 문맥을 유지한다. "
        "Authorization 헤더가 필수이며 누락 시 401을 반환한다."
    ),
)
async def chat(
    request_body: ChatRequest,
    authorization: str = Depends(require_authorization_header),
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> Any:
    session_id = request_body.session_id.strip() if request_body.session_id else str(uuid.uuid4())

    if request_body.stream:
        prefetched_librarian = await service.get_initial_meta(
            session_id=session_id,
            message=request_body.message,
            librarian_id=request_body.librarian_id,
            latitude=request_body.latitude,
            longitude=request_body.longitude,
        )
        headers = {"X-Session-Id": session_id}
        signals = prefetched_librarian.signals if prefetched_librarian is not None else None
        switch_to = (
            prefetched_librarian.switch_to if prefetched_librarian is not None else None
        )

        if signals is None:
            local_fallback = evaluate_local_persona_response(
                message=request_body.message,
                librarian_id=request_body.librarian_id,
                latitude=request_body.latitude,
                longitude=request_body.longitude,
            )
            signals = local_fallback.signals

        if signals is not None:
            headers["X-Signals"] = urllib.parse.quote(signals.model_dump_json())
        if switch_to is not None:
            headers["X-Switch-To"] = urllib.parse.quote(switch_to.model_dump_json())

        return StreamingResponse(
            service.stream_chat(
                session_id=session_id,
                message=request_body.message,
                librarian_id=request_body.librarian_id,
                latitude=request_body.latitude,
                longitude=request_body.longitude,
                auth_token=authorization,
                prefetched_librarian=prefetched_librarian,
            ),
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )

    try:
        answer, switch_to, signals, library_books, recommended_books = await service.chat(
            session_id=session_id,
            message=request_body.message,
            librarian_id=request_body.librarian_id,
            latitude=request_body.latitude,
            longitude=request_body.longitude,
            auth_token=authorization,
        )
    except LibraryAuthError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Library API authentication failed",
        ) from e
    return ChatResponse(
        session_id=session_id,
        message=answer,
        switch_to=switch_to,
        signals=signals,
        library_books=library_books,
        recommended_books=recommended_books,
    )
