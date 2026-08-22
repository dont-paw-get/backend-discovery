"""Redis Testcontainers 기반 /chat 엔드포인트 멀티턴 대화 통합 테스트.

실제 Redis 인프라와 FastAPI 라우터를 통과하며 세션이 누적되는지 검증한다.
Bedrock 및 Tavily 외부 유료 API는 Mock으로 대체하여 결정론적으로 검증한다.
"""

from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from pytest_mock import MockerFixture
from redis.asyncio import Redis
from testcontainers.redis import RedisContainer

from discovery.api.deps import get_book_search_tool
from discovery.infrastructure.cache.chat_session_store import ChatSessionStore
from discovery.infrastructure.search.book_search_tool import BookSearchTool
from discovery.main import create_app

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
def redis_container() -> AsyncGenerator[RedisContainer]:  # type: ignore[misc]
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest_asyncio.fixture
async def redis_client(redis_container: RedisContainer) -> AsyncGenerator[Redis]:
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(6379)
    client: Redis = Redis(host=host, port=int(port), decode_responses=True)
    try:
        yield client
    finally:
        await client.flushall()
        await client.aclose()


@pytest.mark.asyncio
async def test_multi_turn_chat_with_redis(
    redis_client: Redis,
    mocker: MockerFixture,
) -> None:
    # 1. Mock Bedrock and Agent response
    mock_agent_result_1 = MagicMock()
    mock_agent_result_1.message = {
        "role": "assistant",
        "content": [{"text": "추천 도서는 '달러구트 꿈 백화점'입니다."}],
    }
    mock_agent_result_2 = MagicMock()
    mock_agent_result_2.message = {
        "role": "assistant",
        "content": [{"text": "2권도 이어서 읽어보세요."}],
    }

    mock_agent = MagicMock()
    mock_agent.invoke_async = AsyncMock(
        side_effect=[mock_agent_result_1, mock_agent_result_2]
    )

    mock_create_agent = mocker.patch(
        "discovery.application.librarian_service.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_search_tool = MagicMock(spec=BookSearchTool)
    mock_search_tool.as_tool.return_value = MagicMock()

    app = create_app()
    app.state.redis = redis_client
    app.dependency_overrides[get_book_search_tool] = lambda: mock_search_tool

    session_id = "test-e2e-session-1"

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        # Turn 1
        resp1 = await client.post(
            "/api/v1/chat",
            json={"session_id": session_id, "message": "따뜻한 판타지 소설 추천해줘"},
        )
        assert resp1.status_code == 200
        assert resp1.json()["message"] == "추천 도서는 '달러구트 꿈 백화점'입니다."

        # Turn 2
        resp2 = await client.post(
            "/api/v1/chat",
            json={"session_id": session_id, "message": "그 책 후속작도 있어?"},
        )
        assert resp2.status_code == 200
        assert resp2.json()["message"] == "2권도 이어서 읽어보세요."

    # Verify Redis stored both turns (4 messages total: user, assistant, user, assistant)
    store = ChatSessionStore(redis_client, max_turns=20, ttl_seconds=3600)
    history = await store.get_history(session_id)
    assert len(history) == 4
    assert history[0]["content"] == "따뜻한 판타지 소설 추천해줘"
    assert history[1]["content"] == "추천 도서는 '달러구트 꿈 백화점'입니다."
    assert history[2]["content"] == "그 책 후속작도 있어?"
    assert history[3]["content"] == "2권도 이어서 읽어보세요."

    # Verify second agent creation included history from turn 1
    assert mock_create_agent.call_count == 2
    second_call_messages = mock_create_agent.call_args_list[1].kwargs.get("messages")
    assert second_call_messages == [
        {"role": "user", "content": [{"text": "따뜻한 판타지 소설 추천해줘"}]},
        {"role": "assistant", "content": [{"text": "추천 도서는 '달러구트 꿈 백화점'입니다."}]},
    ]
