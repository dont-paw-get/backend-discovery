"""추천 에이전트 대화 API 라우터."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from discovery.api.deps import get_librarian_service
from discovery.api.schemas.chat import ChatRequest, ChatResponse
from discovery.application.librarian_service import LibrarianService

router = APIRouter(prefix="/chat", tags=["Chat"])


@router.post(
    "",
    response_model=ChatResponse,
    responses={
        200: {
            "description": "추천 에이전트 답변 (일반 JSON 또는 stream=True 시 스트리밍 텍스트)",
            "content": {
                "application/json": {},
                "text/plain": {},
            },
        }
    },
    summary="추천 에이전트 도서 추천 대화",
    description=(
        "자연어 질문으로 추천 에이전트에게 도서 추천을 요청한다. "
        "이전 세션 ID를 전달하면 문맥을 유지한다."
    ),
)
async def chat(
    request_body: ChatRequest,
    service: LibrarianService = Depends(get_librarian_service),
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
