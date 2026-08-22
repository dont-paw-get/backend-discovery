"""`/health` 엔드포인트 단위 테스트. 실제 DB/Redis 없이 동작해야 한다."""

import pytest
from httpx import ASGITransport, AsyncClient

from discovery.main import create_app


@pytest.mark.asyncio
async def test_health_returns_ok() -> None:
    app = create_app()
    transport = ASGITransport(app=app)

    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
