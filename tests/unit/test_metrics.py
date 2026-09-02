"""core/metrics.py — Prometheus HTTP 메트릭 미들웨어 및 `/metrics` 엔드포인트 검증.

- `/metrics`가 Micrometer 호환 히스토그램(`http_server_requests_seconds_*`)을 노출
- `application` 라벨이 서비스명으로 채워짐 (트레이스 service.name과 일치)
- 일반 라우트는 `uri` 템플릿과 `outcome`으로 계측되고, probe/`/metrics` 자기 자신은 제외
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from discovery.main import create_app


async def _get(app: object, path: str) -> tuple[int, str, str]:
    transport = ASGITransport(app=app)  # type: ignore[arg-type]
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get(path)
    return resp.status_code, resp.text, resp.headers.get("content-type", "")


@pytest.mark.asyncio
async def test_metrics_endpoint_exposes_micrometer_compatible_histogram() -> None:
    app = create_app()

    async def ping() -> dict[str, str]:
        return {"pong": "ok"}

    app.router.add_api_route("/__metrics_ping__", ping, methods=["GET"])

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        assert (await client.get("/__metrics_ping__")).status_code == 200
        resp = await client.get("/metrics")

    assert resp.status_code == 200
    assert "text/plain" in resp.headers["content-type"]
    body = resp.text
    assert "http_server_requests_seconds_bucket" in body
    assert "http_server_requests_seconds_count" in body
    assert 'application="backend-discovery"' in body
    assert 'uri="/__metrics_ping__"' in body
    assert 'outcome="SUCCESS"' in body


@pytest.mark.asyncio
async def test_probe_and_scrape_paths_are_not_instrumented() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        await client.get("/health")
        await client.get("/api/v1/health")
        await client.get("/metrics")
        body = (await client.get("/metrics")).text

    assert 'uri="/metrics"' not in body
    assert 'uri="/health"' not in body
    assert 'uri="/api/v1/health"' not in body


@pytest.mark.asyncio
async def test_unmatched_route_recorded_as_no_route() -> None:
    app = create_app()
    status, _, _ = await _get(app, "/no/such/path")
    assert status == 404

    _, body, _ = await _get(app, "/metrics")
    assert 'uri="NO_ROUTE"' in body
    assert 'outcome="CLIENT_ERROR"' in body
