"""오케스트레이터 대화 API 라우터."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
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
    summary="오케스트레이터 대화 (도서 추천 및 사서 상담)",
    description=(
        "자연어 질문으로 오케스트레이터에게 대화를 요청한다. "
        "의도에 따라 도서 추천 에이전트 또는 사서 에이전트로 라우팅되며, "
        "이전 세션 ID를 전달하면 문맥을 유지한다."
    ),
)
async def chat(
    request_body: ChatRequest,
    service: OrchestratorService = Depends(get_orchestrator_service),
) -> Any:
    session_id = request_body.session_id.strip() if request_body.session_id else str(uuid.uuid4())

    if request_body.stream:
        return StreamingResponse(
            service.stream_chat(session_id=session_id, message=request_body.message),
            media_type="text/plain; charset=utf-8",
            headers={"X-Session-Id": session_id},
        )

    answer = await service.chat(session_id=session_id, message=request_body.message)
    return ChatResponse(session_id=session_id, message=answer)
