"""SearchMyLibraryTool 단위 테스트."""

import httpx
import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.domain.orchestrator.library_response import LibraryBookItem
from discovery.domain.orchestrator.tools.library_tool import (
    LibraryAuthError,
    SearchMyLibraryTool,
    format_books_for_llm,
)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-secret",
        tavily_api_key="tvly-test",
        library_api_url="http://test-library:8080",
        library_http_timeout_seconds=5.0,
    )


def test_format_books_for_llm_empty() -> None:
    assert format_books_for_llm([], query="") == "사용자의 서재에 등록된 도서가 없습니다."
    assert (
        format_books_for_llm([], query="어린왕자")
        == "사용자의 서재에서 '어린왕자' 관련 도서를 찾지 못했습니다."
    )


def test_format_books_for_llm_success() -> None:
    books = [
        LibraryBookItem(
            book_id=1,
            title="살인자의 기억법",
            author="김영하",
            genre="MYSTERY_THRILLER",
            reading_status="READING",
            progress=45,
        ),
        LibraryBookItem(
            book_id=2,
            title="지구 끝의 온실",
            author="김초엽",
            genre="SCIENCE_FICTION",
            reading_status="COMPLETED",
            progress=100,
        ),
    ]
    formatted = format_books_for_llm(books)
    assert "[내 서재 도서 목록] (총 2권)" in formatted
    assert "1. 제목: 살인자의 기억법" in formatted
    assert "- 저자: 김영하" in formatted
    assert "- 장르: MYSTERY_THRILLER" in formatted
    assert "- 독서 상태: 읽는 중 (진행률: 45%)" in formatted
    assert "2. 제목: 지구 끝의 온실" in formatted
    assert "- 독서 상태: 완독 (진행률: 100%)" in formatted


@pytest.mark.asyncio
async def test_search_missing_auth_token(settings: Settings) -> None:
    tool = SearchMyLibraryTool(settings=settings)
    books = await tool.search(query="김영하", auth_token=None)
    assert books == []


@pytest.mark.asyncio
async def test_search_success_and_filtering(settings: Settings, mocker: MockerFixture) -> None:
    fake_response = {
        "books": [
            {
                "bookId": 101,
                "shelfId": 1,
                "title": "살인자의 기억법",
                "author": "김영하",
                "genre": "MYSTERY_THRILLER",
                "readingStatus": "READING",
                "progress": 45,
            },
            {
                "bookId": 102,
                "shelfId": 1,
                "title": "작별인사",
                "author": "김영하",
                "genre": "SCIENCE_FICTION",
                "readingStatus": "COMPLETED",
                "progress": 100,
            },
            {
                "bookId": 103,
                "shelfId": 2,
                "title": "지구 끝의 온실",
                "author": "김초엽",
                "genre": "SCIENCE_FICTION",
                "readingStatus": "WISH",
                "progress": 0,
            },
        ],
        "page": 0,
        "size": 20,
        "totalElements": 3,
        "totalPages": 1,
    }

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_response
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)

    # 1. 전체 조회
    res_all = await tool.search(auth_token="test-token")
    assert len(res_all) == 3

    # 2. query 필터링 (제목 부분 일치)
    res_title = await tool.search(query="기억법", auth_token="test-token")
    assert len(res_title) == 1
    assert res_title[0].title == "살인자의 기억법"

    # 3. query 필터링 (저자 일치)
    res_author = await tool.search(query="김영하", auth_token="test-token")
    assert len(res_author) == 2

    # 4. query 필터링 (장르 일치)
    res_genre = await tool.search(query="SCIENCE_FICTION", auth_token="test-token")
    assert len(res_genre) == 2

    # 5. reading_status 필터링
    res_status = await tool.search(reading_status="READING", auth_token="test-token")
    assert len(res_status) == 1
    assert res_status[0].title == "살인자의 기억법"


@pytest.mark.asyncio
async def test_search_http_error_graceful_fallback(
    settings: Settings, mocker: MockerFixture
) -> None:
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 500
    mock_resp.text = "Internal Server Error"
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)
    res = await tool.search(query="테스트", auth_token="test-token")
    assert res == []


@pytest.mark.asyncio
async def test_search_401_raises_library_auth_error(
    settings: Settings, mocker: MockerFixture
) -> None:
    """위조/만료된 토큰으로 backend-book이 401을 반환하면 조용히 흡수하지 않고
    LibraryAuthError를 발생시킨다 (ADR 0007 2.2절)."""
    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 401
    mock_resp.text = "Unauthorized"
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)
    with pytest.raises(LibraryAuthError):
        await tool.search(query="테스트", auth_token="forged.invalid.token")


@pytest.mark.asyncio
async def test_as_tool_401_triggers_on_auth_failed_callback(
    settings: Settings, mocker: MockerFixture
) -> None:
    """as_tool()이 LibraryAuthError를 잡아 on_auth_failed 콜백으로 전달하고,
    LLM에는 안전한 안내 문구를 반환한다 (LLM 흐름을 깨지 않음)."""
    tool = SearchMyLibraryTool(settings=settings)
    mocker.patch.object(tool, "search", side_effect=LibraryAuthError("auth failed"))

    auth_failed_holder: list[bool] = []

    def on_auth_failed() -> None:
        auth_failed_holder.append(True)

    tool_fn = tool.as_tool(auth_token="forged.invalid.token", on_auth_failed=on_auth_failed)
    result = await tool_fn(query="테스트")

    assert auth_failed_holder == [True]
    assert "인증" in result


@pytest.mark.asyncio
async def test_as_tool_execution(settings: Settings, mocker: MockerFixture) -> None:
    tool = SearchMyLibraryTool(settings=settings)
    mock_book = LibraryBookItem(
        book_id=101,
        title="살인자의 기억법",
        author="김영하",
        genre="MYSTERY",
        reading_status="READING",
        progress=50,
    )
    mocker.patch.object(tool, "search", return_value=[mock_book])

    fetched_holder: list[list[LibraryBookItem]] = []

    def on_fetched(books: list[LibraryBookItem]) -> None:
        fetched_holder.append(books)

    strands_tool_fn = tool.as_tool(auth_token="jwt-abc-123", on_books_fetched=on_fetched)
    result_text = await strands_tool_fn(query="살인자", author="", reading_status="")

    assert "[내 서재 도서 목록] (총 1권)" in result_text
    assert "살인자의 기억법" in result_text
    # LLM용 포맷팅 텍스트에는 book_id가 노출되지 않아야 함 (사용자 대화문 오염 방지)
    assert "101" not in result_text
    assert "도서 ID" not in result_text
    # 콜백에는 book_id가 온전히 포함된 원본 객체가 수집되어야 함
    assert len(fetched_holder) == 1
    assert fetched_holder[0][0].book_id == 101


@pytest.mark.asyncio
async def test_search_spring_data_page_content_format(
    settings: Settings, mocker: MockerFixture
) -> None:
    """Spring Data JPA 표준 규격인 'content' 키 응답 파싱을 검증한다."""
    fake_spring_page = {
        "content": [
            {
                "bookId": 201,
                "title": "클린 아키텍처",
                "author": "로버트 마틴",
                "genre": "COMPUTER_IT",
                "readingStatus": "READING",
                "progress": 80,
            }
        ],
        "pageable": {"pageNumber": 0, "pageSize": 100},
        "totalElements": 1,
        "totalPages": 1,
    }

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_spring_page
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)
    res = await tool.search(auth_token="test-token")

    assert len(res) == 1
    assert res[0].title == "클린 아키텍처"
    assert res[0].book_id == 201
    assert res[0].author == "로버트 마틴"
    assert res[0].reading_status == "READING"

    # params에 page=0, size=100이 전달되었는지 검증
    call_args, call_kwargs = mock_client.get.call_args
    assert call_kwargs["params"]["page"] == 0
    assert call_kwargs["params"]["size"] == 100


@pytest.mark.asyncio
async def test_search_raw_list_format(settings: Settings, mocker: MockerFixture) -> None:
    """순수 배열([...]) 형태의 응답 파싱을 검증한다."""
    fake_list = [
        {
            "bookId": 301,
            "title": "도둑맞은 집중력",
            "author": "요한 하리",
            "readingStatus": "COMPLETED",
        }
    ]

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_list
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)
    res = await tool.search(auth_token="test-token")

    assert len(res) == 1
    assert res[0].title == "도둑맞은 집중력"


@pytest.mark.asyncio
async def test_search_data_wrapper_format(settings: Settings, mocker: MockerFixture) -> None:
    """data 래핑 형태 ({"data": {"content": [...]}}) 응답 파싱을 검증한다."""
    fake_wrapped = {
        "status": "SUCCESS",
        "data": {
            "content": [
                {
                    "bookId": 401,
                    "title": "사피엔스",
                    "author": "유발 하라리",
                }
            ]
        },
    }

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_wrapped
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)
    res = await tool.search(auth_token="test-token")

    assert len(res) == 1
    assert res[0].title == "사피엔스"


@pytest.mark.asyncio
async def test_search_float_progress_rounded_to_int(
    settings: Settings, mocker: MockerFixture
) -> None:
    """소수점 진행률(예: 88.0165...)이 들어와도 정수(88)로 안전하게 파싱됨을 검증한다."""
    fake_data = {
        "content": [
            {
                "bookId": 501,
                "title": "객체지향의 사실과 오해",
                "author": "조영호",
                "readingStatus": "READING",
                "progress": 88.01652892561984,
            }
        ]
    }

    mock_client = mocker.AsyncMock(spec=httpx.AsyncClient)
    mock_resp = mocker.MagicMock(spec=httpx.Response)
    mock_resp.status_code = 200
    mock_resp.json.return_value = fake_data
    mock_client.get.return_value = mock_resp

    tool = SearchMyLibraryTool(settings=settings, http_client=mock_client)
    res = await tool.search(auth_token="test-token")

    assert len(res) == 1
    assert res[0].title == "객체지향의 사실과 오해"
    assert res[0].progress == 88

