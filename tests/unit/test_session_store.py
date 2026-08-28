"""ChatSessionStore 단위 테스트.

Redis Mock을 사용하여 세션 메타데이터(사서 ID, 좌표) 저장 및 조회, clear 동작을 검증한다.
"""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture
from redis.asyncio import Redis

from discovery.infrastructure.cache.chat_session_store import ChatSessionStore


@pytest.mark.asyncio
async def test_session_meta_get_and_update(mocker: MockerFixture) -> None:
    mock_redis = mocker.MagicMock(spec=Redis)
    mock_redis.get = AsyncMock(return_value=None)
    mock_redis.set = AsyncMock(return_value=True)

    store = ChatSessionStore(mock_redis, max_turns=20, ttl_seconds=3600)

    # 1. 초기 상태 빈 딕셔너리 반환
    meta = await store.get_session_meta("sess-1")
    assert meta == {}

    # 2. 메타데이터 갱신
    await store.update_session_meta("sess-1", librarian_id="stork", latitude=37.5, longitude=127.0)

    mock_redis.set.assert_awaited_once_with(
        "chat:session:sess-1:meta",
        '{"librarian_id": "stork", "latitude": 37.5, "longitude": 127.0}',
        ex=3600,
    )


@pytest.mark.asyncio
async def test_session_clear_deletes_both_history_and_meta(mocker: MockerFixture) -> None:
    mock_redis = mocker.MagicMock(spec=Redis)
    mock_redis.delete = AsyncMock(return_value=2)

    store = ChatSessionStore(mock_redis, max_turns=20, ttl_seconds=3600)

    await store.clear("sess-1")

    mock_redis.delete.assert_awaited_once_with(
        "chat:session:sess-1",
        "chat:session:sess-1:meta",
    )
