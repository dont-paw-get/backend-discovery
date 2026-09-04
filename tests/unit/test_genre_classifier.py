from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_mock import MockerFixture

from discovery.api.schemas.genre import (
    BookClassificationRequest,
    StandardGenre,
)
from discovery.application.genre_classifier_service import GenreClassifierService
from discovery.core.config import Settings
from discovery.domain.genre.classifier import (
    build_classification_prompt,
    match_standard_genre,
    parse_classification_response,
)


def test_build_classification_prompt() -> None:
    """프롬프트 빌더가 도서 ISBN을 올바르게 포함하는지 검증한다."""
    prompt = build_classification_prompt(isbn="9788966263769")
    assert "9788966263769" in prompt
    assert "ISBN" in prompt


def test_build_classification_prompt_strips_whitespace() -> None:
    """프롬프트 빌더가 ISBN 앞뒤 공백을 안전하게 제거하는지 검증한다."""
    prompt = build_classification_prompt(isbn="  9788966263769  ")
    assert "- ISBN: 9788966263769" in prompt


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("SCIENCE_FICTION", StandardGenre.SCIENCE_FICTION),
        ("SF", StandardGenre.SCIENCE_FICTION),
        ("공상과학", StandardGenre.SCIENCE_FICTION),
        ("FANTASY", StandardGenre.FANTASY),
        ("판타지", StandardGenre.FANTASY),
        ("ROMANCE", StandardGenre.ROMANCE),
        ("로맨스", StandardGenre.ROMANCE),
        ("MYSTERY_THRILLER", StandardGenre.MYSTERY_THRILLER),
        ("미스터리/스릴러", StandardGenre.MYSTERY_THRILLER),
        ("추리소설", StandardGenre.MYSTERY_THRILLER),
        ("LITERARY_FICTION", StandardGenre.LITERARY_FICTION),
        ("순수소설/일반소설", StandardGenre.LITERARY_FICTION),
        ("한국소설", StandardGenre.LITERARY_FICTION),
        ("ESSAY", StandardGenre.ESSAY),
        ("에세이", StandardGenre.ESSAY),
        ("POETRY_DRAMA", StandardGenre.POETRY_DRAMA),
        ("시/희곡", StandardGenre.POETRY_DRAMA),
        ("HUMANITIES", StandardGenre.HUMANITIES),
        ("인문학", StandardGenre.HUMANITIES),
        ("HISTORY", StandardGenre.HISTORY),
        ("역사", StandardGenre.HISTORY),
        ("BUSINESS_ECONOMICS", StandardGenre.BUSINESS_ECONOMICS),
        ("경제/경영", StandardGenre.BUSINESS_ECONOMICS),
        ("SELF_HELP", StandardGenre.SELF_HELP),
        ("자기계발", StandardGenre.SELF_HELP),
        ("SCIENCE", StandardGenre.SCIENCE),
        ("과학", StandardGenre.SCIENCE),
        ("ARTS", StandardGenre.ARTS),
        ("예술", StandardGenre.ARTS),
        ("RELIGION", StandardGenre.RELIGION),
        ("종교", StandardGenre.RELIGION),
        ("COMPUTER_IT", StandardGenre.COMPUTER_IT),
        ("컴퓨터/IT", StandardGenre.COMPUTER_IT),
        ("프로그래밍 언어", StandardGenre.COMPUTER_IT),
        ("NONE", StandardGenre.NONE),
        ("기타", StandardGenre.NONE),
        ("알수없는장르XYZ", None),
    ],
)
def test_match_standard_genre(input_str: str, expected: StandardGenre | None) -> None:
    """다양한 문자열이 16개 표준 장르 Enum으로 정확히 매핑되는지 검증한다."""
    assert match_standard_genre(input_str) == expected


def test_parse_classification_response_valid_json() -> None:
    """정상 JSON 문자열이 BookClassificationResponse로 올바르게 파싱되는지 검증한다."""
    raw_text = '{"genre": "COMPUTER_IT", "confidence": 0.95}'
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.COMPUTER_IT
    assert response.confidence == 0.95


def test_parse_classification_response_with_markdown_codeblock() -> None:
    """마크다운 코드블록으로 감싸진 JSON 문자열도 정상 파싱되는지 검증한다."""
    raw_text = """```json
    {
        "genre": "SCIENCE_FICTION",
        "confidence": 0.88
    }
    ```"""
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.SCIENCE_FICTION
    assert response.confidence == 0.88


def test_parse_classification_response_unknown_genre() -> None:
    """표준 장르에 없는 미식별 문자열인 경우 'NONE' fallback 및 신뢰도 0.0을 반환한다."""
    raw_text = '{"genre": "미확인_외계_xyz_123", "confidence": 0.99}'
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.NONE
    assert response.confidence == 0.0


def test_parse_classification_response_invalid_json_fallback() -> None:
    """JSON 형식이 깨졌으나 텍스트 내에 장르 키워드가 있는 경우 텍스트 매칭으로 구제한다."""
    raw_text = "이 책은 전형적인 판타지 장르에 해당합니다."
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.FANTASY
    assert response.confidence == 0.7


def test_parse_classification_response_empty() -> None:
    """빈 응답일 경우 안전하게 'NONE'과 0.0 신뢰도를 반환한다."""
    response = parse_classification_response("")
    assert response.genre == StandardGenre.NONE
    assert response.confidence == 0.0


@pytest.fixture
def mock_settings() -> Settings:
    return Settings(
        redis_url="redis://localhost:6379/0",
        llm_provider="mock",
        internal_api_token="test-token",
        tavily_api_key="test-key",
    )


@pytest.fixture
def bedrock_settings() -> Settings:
    return Settings(
        redis_url="redis://localhost:6379/0",
        llm_provider="bedrock",
        internal_api_token="test-token",
        tavily_api_key="test-key",
    )


@pytest.mark.asyncio
async def test_genre_classifier_service_mock_mode(mock_settings: Settings) -> None:
    """Mock 모드에서 규칙 기반 분류가 정상 동작하는지 검증한다."""
    service = GenreClassifierService(settings=mock_settings)

    # 1. ISBN 내 장르 키워드 매칭
    req1 = BookClassificationRequest(isbn="COMPUTER_IT")
    res1 = await service.classify_genre(req1)
    assert res1.genre == StandardGenre.COMPUTER_IT
    assert res1.confidence == 1.0

    # 2. ISBN 내 한글 장르 키워드 매칭
    req2 = BookClassificationRequest(isbn="역사")
    res2 = await service.classify_genre(req2)
    assert res2.genre == StandardGenre.HISTORY
    assert res2.confidence == 1.0

    # 3. 매칭 없는 일반 숫자 ISBN인 경우 NONE
    req3 = BookClassificationRequest(isbn="9788966263769")
    res3 = await service.classify_genre(req3)
    assert res3.genre == StandardGenre.NONE
    assert res3.confidence == 1.0


@pytest.mark.asyncio
async def test_genre_classifier_service_bedrock_mode(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """Bedrock 모드에서 Strands Agent 호출 및 결과 파싱이 정상 동작하는지 검증한다."""
    mock_agent_instance = MagicMock()
    mock_agent_result = MagicMock()
    mock_agent_result.message = {"content": [{"text": '{"genre": "SCIENCE", "confidence": 0.92}'}]}
    mock_agent_instance.invoke_async = AsyncMock(return_value=mock_agent_result)

    mocker.patch(
        "discovery.application.genre_classifier_service.Agent",
        return_value=mock_agent_instance,
    )
    mocker.patch(
        "discovery.application.genre_classifier_service.BedrockModel",
    )

    service = GenreClassifierService(settings=bedrock_settings)
    req = BookClassificationRequest(isbn="9788934972464")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.SCIENCE
    assert res.confidence == 0.92


@pytest.mark.asyncio
async def test_genre_classifier_service_exception_fallback(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """Bedrock 호출 중 예외가 발생해도 500 에러 대신 'NONE'과 0.0 신뢰도를 반환하는지 검증한다."""
    mocker.patch(
        "discovery.application.genre_classifier_service.Agent",
        side_effect=RuntimeError("AWS Connection Failed"),
    )

    service = GenreClassifierService(settings=bedrock_settings)
    req = BookClassificationRequest(isbn="9788934972464")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.NONE
    assert res.confidence == 0.0



# ---------------------------------------------------------------------------
# CLIAR-282 Task 5: classify_genre 캐시 연동 (히트 시 LLM 호출 완전 스킵)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_classify_genre_returns_cached_result_without_llm_call(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """캐시 히트 시 Bedrock LLM 호출을 전혀 하지 않고 즉시 반환한다."""
    mock_agent_class = mocker.patch("discovery.application.genre_classifier_service.Agent")
    mock_cache = mocker.AsyncMock()
    mock_cache.get.return_value = ("SCIENCE", 0.92)

    service = GenreClassifierService(settings=bedrock_settings, cache=mock_cache)
    req = BookClassificationRequest(isbn="9788934972464")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.SCIENCE
    assert res.confidence == 0.92
    mock_cache.get.assert_awaited_once_with("9788934972464")
    mock_agent_class.assert_not_called()


@pytest.mark.asyncio
async def test_classify_genre_stores_non_none_result_in_cache_on_miss(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """캐시 미스 시 LLM 분류를 수행하고, NONE이 아닌 결과만 캐시에 저장한다."""
    mock_agent_instance = MagicMock()
    mock_agent_result = MagicMock()
    mock_agent_result.message = {"content": [{"text": '{"genre": "SCIENCE", "confidence": 0.92}'}]}
    mock_agent_instance.invoke_async = AsyncMock(return_value=mock_agent_result)
    mocker.patch(
        "discovery.application.genre_classifier_service.Agent",
        return_value=mock_agent_instance,
    )
    mocker.patch("discovery.application.genre_classifier_service.BedrockModel")
    mock_cache = mocker.AsyncMock()
    mock_cache.get.return_value = None

    service = GenreClassifierService(settings=bedrock_settings, cache=mock_cache)
    req = BookClassificationRequest(isbn="9788934972464")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.SCIENCE
    mock_cache.set.assert_awaited_once_with("9788934972464", "SCIENCE", 0.92)


@pytest.mark.asyncio
async def test_classify_genre_does_not_cache_none_result(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """분류 결과가 NONE(미식별)이면 캐시에 저장하지 않는다(불확실한 결과 고정 방지)."""
    mock_agent_instance = MagicMock()
    mock_agent_result = MagicMock()
    mock_agent_result.message = {"content": [{"text": '{"genre": "NONE", "confidence": 0.0}'}]}
    mock_agent_instance.invoke_async = AsyncMock(return_value=mock_agent_result)
    mocker.patch(
        "discovery.application.genre_classifier_service.Agent",
        return_value=mock_agent_instance,
    )
    mocker.patch("discovery.application.genre_classifier_service.BedrockModel")
    mock_cache = mocker.AsyncMock()
    mock_cache.get.return_value = None

    service = GenreClassifierService(settings=bedrock_settings, cache=mock_cache)
    req = BookClassificationRequest(isbn="9788934972464")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.NONE
    mock_cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_classify_genre_works_without_cache(mock_settings: Settings) -> None:
    """cache=None(기존 하위 호환)이면 캐시 관련 동작 없이 기존처럼 동작한다."""
    service = GenreClassifierService(settings=mock_settings)
    req = BookClassificationRequest(isbn="COMPUTER_IT")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.COMPUTER_IT
