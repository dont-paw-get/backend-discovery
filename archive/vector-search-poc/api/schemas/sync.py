"""`/internal/sync-book` 요청/응답 스키마. `docs/api/openapi.yaml`과 1:1이다."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class SyncBookRequest(BaseModel):
    """Basic API가 전달하는 단건 도서 payload.

    실시간 갱신·통합 테스트 용도이며 대량 적재 수단이 아니다
    (`docs/api/decisions/0001-internal-sync-contract.md` 참고).
    """

    book_id: str
    title: str
    author: str
    description: str = ""
    category: str = ""


class SyncBookResponse(BaseModel):
    """동기화 결과. 재전송해도 같은 `book_id`면 동일한 형태를 유지한다(멱등)."""

    model_config = ConfigDict(from_attributes=True)

    book_id: str
    synced_at: datetime = Field(...)
