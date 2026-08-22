"""Basic API 서버 전용 내부 동기화 라우터. `X-Internal-Token` 인증이 필요하다."""

from fastapi import APIRouter, Depends

from discovery.api.deps import get_sync_service, verify_internal_token
from discovery.api.schemas.sync import SyncBookRequest, SyncBookResponse
from discovery.application.sync_service import SyncService

router = APIRouter(
    prefix="/internal",
    tags=["internal"],
    dependencies=[Depends(verify_internal_token)],
)


@router.post("/sync-book", response_model=SyncBookResponse)
async def sync_book(
    payload: SyncBookRequest,
    sync_service: SyncService = Depends(get_sync_service),
) -> SyncBookResponse:
    """Basic API가 보낸 단건 도서 데이터를 임베딩해 읽기 모델에 멱등 upsert한다.

    실시간 갱신·통합 테스트 전용이며 대량 적재 수단이 아니다
    (`docs/api/decisions/0001-internal-sync-contract.md` 참고).
    """
    return await sync_service.sync(payload)
