"""오케스트레이터 대화 API 라우터."""

import urllib.parse
import uuid
from typing import Any

from fastapi import APIRouter, Depends, Header
from fastapi.responses import StreamingResponse

from discovery.api.deps import get_orchestrator_service
from discovery.api.schemas.chat import ChatRequest, ChatResponse
from discovery.application.orchestrator_service import OrchestratorService

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
        }
    },
    summary="오케스트레이터 대화 (도서 추천, 서재 검색, 사서 상담)",
    description=(
        "자연어 질문으로 오케스트레이터에게 대화를 요청한다. "
        "의도에 따라 내 서재 도서 검색, 외부 도서 추천 또는 사서 에이전트로 라우팅되며, "
        "이전 세션 ID를 전달하면 문맥을 유지한다."
    ),
)
async def chat(
    request_body: ChatRequest,
    authorization: str | None = Header(default=None, alias="Authorization"),
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> Any:
    session_id = request_body.session_id.strip() if request_body.session_id else str(uuid.uuid4())

    if request_body.stream:
        signals, switch_to = await service.get_initial_meta(
            session_id=session_id,
            message=request_body.message,
            librarian_id=request_body.librarian_id,
            latitude=request_body.latitude,
            longitude=request_body.longitude,
        )
        headers = {"X-Session-Id": session_id}
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
            ),
            media_type="text/plain; charset=utf-8",
            headers=headers,
        )

    answer, switch_to, signals, library_books = await service.chat(
        session_id=session_id,
        message=request_body.message,
        librarian_id=request_body.librarian_id,
        latitude=request_body.latitude,
        longitude=request_body.longitude,
        auth_token=authorization,
    )
    return ChatResponse(
        session_id=session_id,
        message=answer,
        switch_to=switch_to,
        signals=signals,
        library_books=library_books,
    )
