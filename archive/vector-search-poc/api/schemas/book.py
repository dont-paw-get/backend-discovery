"""도서 응답 DTO. 목록/상세 스키마를 분리해 목록 쿼리가 무거운 필드를 안 실어도 되게 한다."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BookSummary(BaseModel):
    """목록 응답용 경량 DTO. embedding처럼 무거운 필드는 포함하지 않는다."""

    model_config = ConfigDict(from_attributes=True)

    book_id: str
    title: str
    author: str
    category: str
    synced_at: datetime


class BookDetail(BaseModel):
    """상세 응답용 DTO. description을 포함해 목록보다 필드가 많다."""

    model_config = ConfigDict(from_attributes=True)

    book_id: str
    title: str
    author: str
    description: str
    category: str
    synced_at: datetime
