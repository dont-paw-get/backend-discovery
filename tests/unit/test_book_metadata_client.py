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


# ---------------------------------------------------------------------------
# CLIAR-237 재수정(2026-09-02 실측): 2단 조회 및 Authorization 패스스루
# by-title-author는 ISBN은 주지만 totalPages=null → 그 ISBN으로 search?isbn= 재조회.
# 두 엔드포인트 모두 무인증 401 → 사용자 Bearer 토큰 패스스루 필수.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fetch_by_title_author_falls_back_to_isbn_lookup_when_pages_null(
    settings: Settings, mocker: MockerFixture
) -> None:
    # 1단계 by-title-author: ISBN은 있으나 totalPages=null (실측된 실제 동작)
    resp_title_author = mocker.MagicMock(spec=httpx.Response)
    resp_title_author.status_code = 200
    resp_title_author.json.return_value = {
        "book": {
            "title": "사피엔스",
            "author": "유발 하라리",
            "isbn": "9788934972464",
            "totalPages": None,
        }
    }
    # 2단계 search?isbn=: 같은 책의 totalPages가 채워져 반환됨
    resp_isbn = mocker.MagicMock(spec=httpx.Response)
    resp_isbn.status_code = 200
    resp_isbn.json.return_value = {
        "alreadyRegistered": False,
        "book": {"title": "사피엔스", "isbn": "9788934972464", "totalPages": 648},
    }

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.side_effect = [resp_title_author, resp_isbn]

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author(
        "사피엔스", "유발 하라리", auth_token="Bearer test-jwt"
    )

    # 2단 조회로 정확한 페이지수를 확보해야 한다.
    assert result == 648
    assert mock_client.get.await_count == 2

    first_call, second_call = mock_client.get.await_args_list
    # 1단계는 by-title-author 엔드포인트, 2단계는 획득한 ISBN으로 search
    assert first_call.args[0] == "http://test-book:8080/api/v1/books/search/by-title-author"
    assert second_call.args[0] == "http://test-book:8080/api/v1/books/search"
    assert second_call.kwargs["params"] == {"isbn": "9788934972464"}

    # 두 호출 모두 Authorization 헤더가 실려야 한다(무인증 401 방지).
    assert first_call.kwargs["headers"]["Authorization"] == "Bearer test-jwt"
    assert second_call.kwargs["headers"]["Authorization"] == "Bearer test-jwt"


@pytest.mark.asyncio
async def test_fetch_by_title_author_skips_isbn_lookup_when_pages_present(
    settings: Settings, mocker: MockerFixture
) -> None:
    # by-title-author가 예외적으로 totalPages를 직접 채워주면(향후 backend-book 개선)
    # 2단계 재조회 없이 그 값을 그대로 쓴다.
    resp = mocker.MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {
        "book": {"title": "어린 왕자", "isbn": "9788932917245", "totalPages": 136}
    }
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author("어린 왕자", "앙투안 드 생텍쥐페리")

    assert result == 136
    # 페이지수가 이미 있으므로 단 1회만 호출한다.
    assert mock_client.get.await_count == 1


@pytest.mark.asyncio
async def test_fetch_by_title_author_returns_none_when_no_isbn_and_no_pages(
    settings: Settings, mocker: MockerFixture
) -> None:
    # totalPages도 null이고 ISBN도 없으면 재조회할 수 없어 None.
    resp = mocker.MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = {"book": {"title": "제목만 있는 책", "totalPages": None}}
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_client.get.return_value = resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    result = await client.fetch_by_title_author("제목만 있는 책", "저자")

    assert result is None
    assert mock_client.get.await_count == 1


@pytest.mark.asyncio
async def test_fetch_total_pages_sends_authorization_header(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"book": {"totalPages": 200}}
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    # 이미 "Bearer " 접두사가 있으면 그대로, 없으면 붙여준다.
    await client.fetch_total_pages("9788932917245", auth_token="raw-token")

    headers = mock_client.get.await_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer raw-token"


@pytest.mark.asyncio
async def test_fetch_no_authorization_header_when_token_missing(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = {"book": {"totalPages": 200}}
    mock_client.get.return_value = mock_resp

    client = BookMetadataClient(settings=settings, http_client=mock_client)
    await client.fetch_total_pages("9788932917245")

    headers = mock_client.get.await_args.kwargs["headers"]
    assert "Authorization" not in headers
