"""`client` 픽스처(httpx.AsyncClient + DI 오버라이드)가 정상 동작하는지 확인하는 스모크 테스트.
실제 Task 6/13에서 DB 세션을 쓰는 라우터가 생기면 이 테스트는 해당 라우터로 대체된다.
"""

import pytest
from httpx import AsyncClient

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_client_fixture_reaches_health_endpoint(client: AsyncClient) -> None:
    response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
