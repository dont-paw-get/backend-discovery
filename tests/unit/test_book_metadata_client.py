"""BookMetadataClient 단위 테스트 (CLIAR-237: 알라딘 실조회 페이지수 검증)."""

import httpx
import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.domain.orchestrator.tools.book_metadata_client import BookMetadataClient


@pytest.fixture
def settings() -> Settings:
    return Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-secret",
        tavily_api_key="tvly-test",
        book_metadata_api_url="http://test-book:8080",
        book_metadata_timeout_seconds=2.0,
    )


@pytest.mark.asyncio
async def test_fetch_total_pages_returns_value_from_book(
    settings: Settings, mocker: MockerFixture
) -> None:
    # alreadyRegistered=false + book 케이스 (신규 알라딘 조회)
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "alreadyRegistered": False,
        "book": {
            "title": "어린 왕자",
            "author": "앙투안 드 생텍쥐페리",
            "isbn": "9788932917245",
            "publisher": "열린책들",
            "publishedDate": "2015-10-20",
            "totalPages": 160,
            "coverUrl": "https://example.com/covers/9788932917245.jpg",
        },
    }
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_total_pages("9788932917245")

    assert result == 160
    mock_client.get.assert_awaited_once()
    call_args = mock_client.get.await_args
    assert call_args.args[0] == "http://test-book:8080/api/v1/books/search"
    assert call_args.kwargs["params"] == {"isbn": "9788932917245"}


@pytest.mark.asyncio
async def test_fetch_total_pages_returns_none_when_book_missing(
    settings: Settings, mocker: MockerFixture
) -> None:
    # 알라딘에도 없는 경우: book 키 자체가 응답에서 생략됨
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"alreadyRegistered": False}
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_total_pages("0000000000000")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_total_pages_returns_none_on_non_200_status(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_total_pages("9788932917245")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_total_pages_returns_none_on_network_error(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectTimeout("timeout")

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_total_pages("9788932917245")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_total_pages_returns_none_for_empty_isbn(settings: Settings) -> None:
    client = BookMetadataClient(settings=settings)
    assert await client.fetch_total_pages("") is None
    assert await client.fetch_total_pages("   ") is None


@pytest.mark.asyncio
async def test_fetch_total_pages_uses_library_book_when_already_registered(
    settings: Settings, mocker: MockerFixture
) -> None:
    # alreadyRegistered=true 케이스: libraryBook 키가 book과 동일 스키마라고 가정하고 처리
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "alreadyRegistered": True,
        "libraryBook": {
            "title": "어린 왕자",
            "totalPages": 160,
        },
    }
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_total_pages("9788932917245")

    assert result == 160



# ---------------------------------------------------------------------------
# CLIAR-237 후속: 제목·저자 교집합 검색 (GET /api/v1/books/search/by-title-author)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_by_title_author_returns_value_from_book(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "book": {
            "title": "어린 왕자",
            "author": "앙투안 드 생텍쥐페리",
            "isbn": "9788932917245",
            "publisher": "열린책들",
            "publishedDate": "2015-10-20",
            "totalPages": 136,
            "coverUrl": "https://image.aladin.co.kr/product/6853/49/coversum/8932917248_2.jpg",
        }
    }
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author("어린 왕자", "앙투안 드 생텍쥐페리")

    assert result == 136
    mock_client.get.assert_awaited_once()
    call_args = mock_client.get.await_args
    assert call_args.args[0] == "http://test-book:8080/api/v1/books/search/by-title-author"
    assert call_args.kwargs["params"] == {
        "title": "어린 왕자",
        "author": "앙투안 드 생텍쥐페리",
    }


@pytest.mark.asyncio
async def test_fetch_by_title_author_returns_none_when_intersection_empty(
    settings: Settings, mocker: MockerFixture
) -> None:
    # 교집합이 없으면 200 응답이지만 book 필드 자체가 생략된다.
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {}
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author("존재하지 않는 책", "존재하지 않는 저자")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_by_title_author_returns_none_on_non_200_status(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author("어린 왕자", "앙투안 드 생텍쥐페리")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_by_title_author_returns_none_on_network_error(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = httpx.ConnectTimeout("timeout")

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author("어린 왕자", "앙투안 드 생텍쥐페리")

    assert result is None


@pytest.mark.asyncio
async def test_fetch_by_title_author_returns_none_for_empty_title_or_author(
    settings: Settings,
) -> None:
    client = BookMetadataClient(settings=settings)
    assert await client.fetch_by_title_author("", "저자") is None
    assert await client.fetch_by_title_author("제목", "") is None
    assert await client.fetch_by_title_author("   ", "   ") is None
