"""RecommendBooksTool 단위 테스트.

실제 AWS/Bedrock/Tavily 호출 없이 mocker로 에이전트와 도구를 모킹하여
추천 에이전트 호출, count 인자 전달/clamp 및 텍스트 반환 동작을 검증한다.
"""

from unittest.mock import AsyncMock

import pytest
from pytest_mock import MockerFixture

from discovery.core.config import Settings
from discovery.domain.orchestrator.tools.recommend_tool import RecommendBooksTool


@pytest.mark.asyncio
async def test_recommend_tool_calls_create_librarian_agent(mocker: MockerFixture) -> None:
    mock_search_tool = mocker.MagicMock()
    mock_search_as_tool = mocker.MagicMock()
    mock_search_tool.as_tool.return_value = mock_search_as_tool

    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
        librarian_model_id="anthropic.claude-3-haiku-20240307-v1:0",
        aws_region="us-east-1",
    )

    mock_agent = mocker.MagicMock()
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": "### 📖 지구 끝의 온실\n- **저자**: 김초엽"}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mock_create_librarian = mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
    )

    result_text = await tool_instance.recommend(query="SF 소설 추천해줘", count=1)

    assert result_text == "### 📖 지구 끝의 온실\n- **저자**: 김초엽"

    mock_create_librarian.assert_called_once_with(
        model_id="anthropic.claude-3-haiku-20240307-v1:0",
        region_name="us-east-1",
        boto_session=None,
        librarian_id=None,
        tools=[mock_search_as_tool],
        enable_prompt_caching=False,
    )
    expected_prompt = (
        "SF 소설 추천해줘\n\n"
        "[요청] 반드시 1권의 도서만 추천해주세요. "
        "search_books 도구는 정확히 1회만 호출하고, 그 한 번의 검색어로 "
        "1권 분량의 후보와 서지 정보를 한꺼번에 확보하세요. "
        "인사말이나 서두/맺음 멘트는 일절 쓰지 말고, "
        "오직 '### 📖 {도서 제목}' 카드 규격만 바로 출력하세요."
    )
    mock_agent.invoke_async.assert_awaited_once_with(prompt=expected_prompt)


@pytest.mark.asyncio
async def test_recommend_tool_as_tool_execution(mocker: MockerFixture) -> None:
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
    )
    tool_instance.recommend = AsyncMock(return_value="추천 도서입니다.")  # type: ignore[method-assign]

    tool_func = tool_instance.as_tool(auth_token="Bearer test-jwt")

    # Strands @tool로 데코레이트된 함수 실행 검증 (기본값 count=2 및 명시적 count=3)
    result_default = await tool_func(query="인문학 책 추천")
    assert result_default == "추천 도서입니다."
    tool_instance.recommend.assert_awaited_with(
        query="인문학 책 추천",
        count=2,
        librarian_id=None,
        session_id=None,
        auth_token="Bearer test-jwt",
    )

    result_custom = await tool_func(query="소설 3권 추천", count=3)
    assert result_custom == "추천 도서입니다."
    tool_instance.recommend.assert_awaited_with(
        query="소설 3권 추천",
        count=3,
        librarian_id=None,
        session_id=None,
        auth_token="Bearer test-jwt",
    )


@pytest.mark.asyncio
async def test_recommend_tool_truncates_surplus_books(mocker: MockerFixture) -> None:
    # 하위 에이전트가 2권을 생성했으나 count=1을 요청한 경우 1권만 반환되는지 결과 검증
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    two_books_text = (
        "요청하신 도서입니다.\n\n"
        "### 📖 불편한 편의점\n- **저자**: 김호연\n\n"
        "### 📖 달러구트 꿈 백화점\n- **저자**: 이미예"
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {
        "role": "assistant",
        "content": [{"text": two_books_text}],
    }
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)

    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
    )

    result_text = await tool_instance.recommend(query="책 1권 추천해줘", count=1)

    assert "### 📖 불편한 편의점" in result_text
    assert "### 📖 달러구트 꿈 백화점" not in result_text
    assert result_text.count("### 📖") == 1



# ---------------------------------------------------------------------------
# CLIAR-237 후속: 제목·저자 기반 알라딘 조회로 페이지수 검증
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_verifies_page_count_via_title_author(
    mocker: MockerFixture,
) -> None:
    # LLM이 "약 300쪽"처럼 근사치를 생성해도, 제목/저자 검증에 성공하면 정확한 값으로
    # 교체되어야 한다.
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = (
        "### 📖 돈의 심리학\n"
        "- **저자**: 모건 하우절 (약 300쪽)\n"
        "- **추천 이유**: 재테크가 아니라 돈을 대하는 심리를 다룹니다."
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(return_value=None)
    mock_metadata_client.fetch_isbn_only = AsyncMock(return_value="9788934972464")
    mock_metadata_client.fetch_total_pages = AsyncMock(return_value=352)
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
    )

    result_text = await tool_instance.recommend(
        query="돈에 관한 책 추천해줘", count=1, auth_token="Bearer test-jwt"
    )

    # auth_token이 fetch_isbn_only까지 패스스루되는지 검증(무인증 401 방지).
    mock_metadata_client.fetch_isbn_only.assert_awaited_once_with(
        "돈의 심리학", "모건 하우절", auth_token="Bearer test-jwt"
    )
    mock_metadata_client.fetch_total_pages.assert_awaited_once_with(
        "9788934972464", auth_token="Bearer test-jwt"
    )
    assert "(352쪽)" in result_text
    assert "약 300쪽" not in result_text


@pytest.mark.asyncio
async def test_recommend_keeps_llm_value_when_metadata_lookup_fails(
    mocker: MockerFixture,
) -> None:
    # 알라딘 조회가 실패(None, 예: 교집합 없음)하면 LLM이 생성한 기존 값을 그대로
    # 유지해야 한다.
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = (
        "### 📖 돈의 심리학\n"
        "- **저자**: 모건 하우절 (약 300쪽)\n"
        "- **추천 이유**: 재테크가 아니라 돈을 대하는 심리를 다룹니다."
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(return_value=None)
    mock_metadata_client.fetch_isbn_only = AsyncMock(return_value=None)
    mock_metadata_client.fetch_total_pages = AsyncMock(return_value=None)
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
    )

    result_text = await tool_instance.recommend(query="돈에 관한 책 추천해줘", count=1)

    # 검증 실패 시 기존 LLM 생성 표기를 그대로 보존한다(더 나쁜 값으로 덮어쓰지 않음).
    assert "약 300쪽" in result_text


@pytest.mark.asyncio
async def test_recommend_skips_verification_without_metadata_client(
    mocker: MockerFixture,
) -> None:
    # book_metadata_client가 배선되지 않은 경우 검증 없이 원본을 그대로 반환한다.
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = (
        "### 📖 어린 왕자\n"
        "- **저자**: 앙투안 드 생텍쥐페리\n"
        "- **추천 이유**: 어른을 위한 동화입니다."
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        # book_metadata_client 미배선
    )

    result_text = await tool_instance.recommend(query="동화책 추천해줘", count=1)

    assert result_text == raw_text



@pytest.mark.asyncio
async def test_recommend_backfills_missing_genre_via_classifier(mocker: MockerFixture) -> None:
    """CLIAR-282: LLM이 `- **장르**:` 라인을 빼먹은 도서는 backend-book에서 얻은 ISBN으로
    GenreClassifierService를 재호출해 결정론적으로 장르를 보강한다."""
    from discovery.api.schemas.genre import BookClassificationResponse, StandardGenre

    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    # 장르 라인이 통째로 빠진 실제 dev 재현 케이스.
    raw_text = (
        "### 📖 총, 균, 쇠\n"
        "- **저자**: 재레드 다이아몬드 (784쪽)\n"
        "- 문명의 흥망성쇠를 파헤치는 지적 모험이다."
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(return_value=None)
    mock_metadata_client.fetch_isbn_only = AsyncMock(return_value="9788934972464")
    mock_metadata_client.fetch_total_pages = AsyncMock(return_value=None)
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    mock_genre_service = mocker.MagicMock()
    mock_genre_service.classify_genre = AsyncMock(
        return_value=BookClassificationResponse(genre=StandardGenre.HISTORY, confidence=0.9)
    )

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
        genre_classifier_service=mock_genre_service,
    )

    result_text = await tool_instance.recommend(query="역사책 추천해줘", count=1)

    mock_genre_service.classify_genre.assert_awaited_once()
    await_args = mock_genre_service.classify_genre.await_args
    assert await_args is not None
    called_request = await_args.args[0]
    assert called_request.isbn == "9788934972464"
    assert "- **장르**: HISTORY" in result_text


@pytest.mark.asyncio
async def test_recommend_keeps_existing_genre_without_calling_classifier(
    mocker: MockerFixture,
) -> None:
    """이미 `- **장르**:` 라인이 정상적으로 있으면(NONE이 아니면) classifier를 호출하지
    않는다(불필요한 LLM 재호출 방지)."""
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = (
        "### 📖 지구 끝의 온실\n"
        "- **저자**: 김초엽\n"
        "- **추천 이유**: SF 감성 소설.\n"
        "- **장르**: SCIENCE_FICTION"
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(return_value=None)
    mock_metadata_client.fetch_isbn_only = AsyncMock(return_value="9791162341234")
    mock_metadata_client.fetch_total_pages = AsyncMock(return_value=None)
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    mock_genre_service = mocker.MagicMock()

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
        genre_classifier_service=mock_genre_service,
    )

    await tool_instance.recommend(query="SF 소설 추천해줘", count=1)

    mock_genre_service.classify_genre.assert_not_called()


@pytest.mark.asyncio
async def test_recommend_skips_genre_backfill_without_classifier_service(
    mocker: MockerFixture,
) -> None:
    """genre_classifier_service가 배선되지 않으면 장르 보강을 시도하지 않고 원본을
    그대로 반환한다(기존 동작 무변화, 하위 호환)."""
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = "### 📖 총, 균, 쇠\n- **저자**: 재레드 다이아몬드 (784쪽)"
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(return_value=None)
    mock_metadata_client.fetch_isbn_only = AsyncMock(return_value="9788934972464")
    mock_metadata_client.fetch_total_pages = AsyncMock(return_value=None)
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
        # genre_classifier_service 미배선
    )

    result_text = await tool_instance.recommend(query="역사책 추천해줘", count=1)

    assert "- **장르**:" not in result_text



# ---------------------------------------------------------------------------
# CLIAR-282 병렬화: 페이지수 2단계 조회와 장르 분류 LLM 호출의 동시 실행
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_recommend_runs_page_lookup_and_genre_classification_concurrently(
    mocker: MockerFixture,
) -> None:
    """캐시 미스 시 1단계(ISBN 확보) 이후, 서로 의존성이 없는 "페이지수 2단계 조회"와
    "장르 분류 LLM 호출"이 순차가 아니라 동시에 실행되는지 타이밍으로 검증한다.

    두 호출 모두 0.05초를 지연시켰을 때, 순차라면 총 0.1초 이상 걸리지만 병렬이면
    max(0.05, 0.05)=0.05초 근처로 끝나야 한다.
    """
    import asyncio as _asyncio

    from discovery.api.schemas.genre import BookClassificationResponse, StandardGenre

    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = "### 📖 총, 균, 쇠\n- **저자**: 재레드 다이아몬드 (784쪽)"
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    delay_seconds = 0.05

    async def _delayed_fetch_total_pages(isbn: str, auth_token: str | None = None) -> int:
        await _asyncio.sleep(delay_seconds)
        return 500

    async def _delayed_classify_genre(request: object) -> BookClassificationResponse:
        await _asyncio.sleep(delay_seconds)
        return BookClassificationResponse(genre=StandardGenre.HISTORY, confidence=0.9)

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(return_value=None)
    mock_metadata_client.fetch_isbn_only = AsyncMock(return_value="9788934972464")
    mock_metadata_client.fetch_total_pages = _delayed_fetch_total_pages
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    mock_genre_service = mocker.MagicMock()
    mock_genre_service.classify_genre = _delayed_classify_genre

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
        genre_classifier_service=mock_genre_service,
    )

    start = _asyncio.get_event_loop().time()
    await tool_instance.recommend(query="역사책 추천해줘", count=1)
    elapsed = _asyncio.get_event_loop().time() - start

    # 순차라면 2 * delay_seconds(0.1초) 이상, 병렬이면 delay_seconds(0.05초) 근처.
    # 테스트 환경 오버헤드를 감안해 1.5배 여유를 둔 임계값으로 검증한다.
    assert elapsed < delay_seconds * 1.5


@pytest.mark.asyncio
async def test_recommend_uses_cached_isbn_and_pages_without_http_call(
    mocker: MockerFixture,
) -> None:
    """캐시 히트 시 알라딘 HTTP 호출(fetch_isbn_only/fetch_total_pages) 없이 캐시된
    값을 즉시 사용한다."""
    mock_search_tool = mocker.MagicMock()
    settings = Settings(
        redis_url="redis://localhost:6379",
        internal_api_token="test-token",
        tavily_api_key="test-tavily-key",
    )

    mock_agent = mocker.MagicMock()
    raw_text = (
        "### 📖 총, 균, 쇠\n"
        "- **저자**: 재레드 다이아몬드 (약 700쪽)\n"
        "- **추천 이유**: 문명의 흥망성쇠를 다룬다."
    )
    mock_result = mocker.MagicMock()
    mock_result.message = {"role": "assistant", "content": [{"text": raw_text}]}
    mock_agent.invoke_async = AsyncMock(return_value=mock_result)
    mocker.patch(
        "discovery.domain.orchestrator.tools.recommend_tool.create_librarian_agent",
        return_value=mock_agent,
    )

    mock_metadata_client = mocker.MagicMock()
    mock_metadata_client.get_cached_isbn_and_pages = AsyncMock(
        return_value=("9788934972464", 784)
    )
    mock_metadata_client.fetch_isbn_only = AsyncMock()
    mock_metadata_client.fetch_total_pages = AsyncMock()
    mock_metadata_client.cache_isbn_and_pages = AsyncMock()

    tool_instance = RecommendBooksTool(
        book_search_tool=mock_search_tool,
        settings=settings,
        book_metadata_client=mock_metadata_client,
    )

    result_text = await tool_instance.recommend(query="역사책 추천해줘", count=1)

    assert "(784쪽)" in result_text
    mock_metadata_client.fetch_isbn_only.assert_not_awaited()
    mock_metadata_client.fetch_total_pages.assert_not_awaited()
    mock_metadata_client.cache_isbn_and_pages.assert_not_awaited()
