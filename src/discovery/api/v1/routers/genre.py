"""도서 표준 장르 분류 라우터."""

from fastapi import APIRouter, Depends, status

from discovery.api.deps import get_genre_classifier_service
from discovery.api.schemas.genre import (
    BookClassificationRequest,
    BookClassificationResponse,
)
from discovery.application.genre_classifier_service import GenreClassifierService

router = APIRouter(tags=["Genre"])


@router.post(
    "/classify-genre",
    response_model=BookClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="도서 표준 장르 분류",
    description=(
        "도서 메타데이터(제목, 저자, 원본 카테고리)를 분석하여 "
        "16개 표준 장르 중 하나와 신뢰도를 분류하여 반환합니다."
    ),
)
async def classify_genre(
    request: BookClassificationRequest,
    service: GenreClassifierService = Depends(get_genre_classifier_service),
) -> BookClassificationResponse:
    """도서 정보를 기반으로 ERD 표준 16개 장르 중 1개로 분류한다."""
    return await service.classify_genre(request)
