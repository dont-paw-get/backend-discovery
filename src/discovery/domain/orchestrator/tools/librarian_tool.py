"""사서 에이전트(backend-librarian)와 HTTP로 통신하는 도구."""

import logging
from typing import Any

import httpx
from strands import tool

from discovery.core.config import Settings

logger = logging.getLogger(__name__)

LIBRARIAN_UNAVAILABLE_MESSAGE = "사서 에이전트 서비스가 현재 준비 중입니다."


class ConsultLibrarianTool:
    """원격 사서 에이전트를 오케스트레이터의 Agent-as-a-Tool로 호출하는 도구."""

    def __init__(
        self,
        settings: Settings,
        http_client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings
        self._http_client = http_client

    async def consult(self, message: str, session_id: str | None = None) -> str:
        """사서 에이전트 HTTP API를 호출하여 응답을 받는다.

        URL 미설정 또는 네트워크/서버 에러 발생 시 예외를 전파하지 않고
        스텁 준비 중 메시지를 반환한다.
        """
        if not self._settings.librarian_agent_url:
            logger.info("librarian_agent_url is not configured, returning fallback stub.")
            return LIBRARIAN_UNAVAILABLE_MESSAGE

        url = f"{self._settings.librarian_agent_url.rstrip('/')}/api/v1/chat"
        payload = {"message": message, "session_id": session_id}

        try:
            if self._http_client is not None:
                response = await self._http_client.post(url, json=payload, timeout=10.0)
            else:
                async with httpx.AsyncClient() as client:
                    response = await client.post(url, json=payload, timeout=10.0)

            if response.status_code == 200:
                data = response.json()
                if (
                    isinstance(data, dict)
                    and "message" in data
                    and isinstance(data["message"], str)
                ):
                    return data["message"]
            logger.warning(
                "Librarian agent responded with status %d: %s",
                response.status_code,
                response.text,
            )
            return LIBRARIAN_UNAVAILABLE_MESSAGE
        except Exception:
            logger.exception("Failed to connect to librarian agent service at %s", url)
            return LIBRARIAN_UNAVAILABLE_MESSAGE

    def as_tool(self) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다."""

        @tool(name="consult_librarian")
        async def consult_librarian_tool(message: str) -> str:
            """도서관 사서와의 페르소나 대화, 감정 및 독서 고민 상담 등이 필요할 때 호출합니다.

            Args:
                message: 사서에게 전달할 사용자의 이야기나 고민 내용
                    (예: '요즘 마음이 허전해요', '사서님과 이야기하고 싶어요').
            """
            return await self.consult(message)

        return consult_librarian_tool
