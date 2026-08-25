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
    """프롬프트 빌더가 도서 제목, 저자, 원본 카테고리를 올바르게 포함하는지 검증한다."""
    prompt = build_classification_prompt(
        title="파이썬 코딩의 기술",
        author="브렛 슬라킨",
        raw_category="국내도서 > 컴퓨터/모바일",
    )
    assert "파이썬 코딩의 기술" in prompt
    assert "브렛 슬라킨" in prompt
    assert "국내도서 > 컴퓨터/모바일" in prompt


def test_build_classification_prompt_empty_optional_fields() -> None:
    """저자나 원본 카테고리가 비어 있을 때 기본 문구가 들어가는지 검증한다."""
    prompt = build_classification_prompt(title="제목만 있는 책")
    assert "제목만 있는 책" in prompt
    assert "정보 없음" in prompt


@pytest.mark.parametrize(
    ("input_str", "expected"),
    [
        ("SF", StandardGenre.SF),
        ("판타지", StandardGenre.FANTASY),
        ("로맨스", StandardGenre.ROMANCE),
        ("미스터리/스릴러", StandardGenre.MYSTERY_THRILLER),
        ("추리소설", StandardGenre.MYSTERY_THRILLER),
        ("순수소설/일반소설", StandardGenre.GENERAL_FICTION),
        ("한국소설", StandardGenre.GENERAL_FICTION),
        ("에세이", StandardGenre.ESSAY),
        ("시/희곡", StandardGenre.POETRY_PLAY),
        ("인문학", StandardGenre.HUMANITIES),
        ("역사", StandardGenre.HISTORY),
        ("경제/경영", StandardGenre.BUSINESS_ECONOMY),
        ("자기계발", StandardGenre.SELF_HELP),
        ("과학", StandardGenre.SCIENCE),
        ("예술", StandardGenre.ART),
        ("종교", StandardGenre.RELIGION),
        ("컴퓨터/IT", StandardGenre.IT_COMPUTER),
        ("프로그래밍 언어", StandardGenre.IT_COMPUTER),
        ("기타", StandardGenre.ETC),
        ("알수없는장르XYZ", None),
    ],
)
def test_match_standard_genre(input_str: str, expected: StandardGenre | None) -> None:
    """다양한 문자열이 16개 표준 장르 Enum으로 정확히 매핑되는지 검증한다."""
    assert match_standard_genre(input_str) == expected


def test_parse_classification_response_valid_json() -> None:
    """정상 JSON 문자열이 BookClassificationResponse로 올바르게 파싱되는지 검증한다."""
    raw_text = '{"genre": "컴퓨터/IT", "confidence": 0.95}'
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.IT_COMPUTER
    assert response.confidence == 0.95


def test_parse_classification_response_with_markdown_codeblock() -> None:
    """마크다운 코드블록으로 감싸진 JSON 문자열도 정상 파싱되는지 검증한다."""
    raw_text = """```json
    {
        "genre": "SF",
        "confidence": 0.88
    }
    ```"""
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.SF
    assert response.confidence == 0.88


def test_parse_classification_response_unknown_genre() -> None:
    """표준 장르에 없는 미식별 문자열인 경우 '기타' fallback 및 신뢰도 0.0을 반환한다."""
    raw_text = '{"genre": "미확인_외계_xyz_123", "confidence": 0.99}'
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.ETC
    assert response.confidence == 0.0


def test_parse_classification_response_invalid_json_fallback() -> None:
    """JSON 형식이 깨졌으나 텍스트 내에 장르 키워드가 있는 경우 텍스트 매칭으로 구제한다."""
    raw_text = "이 책은 전형적인 판타지 장르에 해당합니다."
    response = parse_classification_response(raw_text)
    assert response.genre == StandardGenre.FANTASY
    assert response.confidence == 0.7


def test_parse_classification_response_empty() -> None:
    """빈 응답일 경우 안전하게 '기타'와 0.0 신뢰도를 반환한다."""
    response = parse_classification_response("")
    assert response.genre == StandardGenre.ETC
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

    # 1. raw_category 기반 분류
    req1 = BookClassificationRequest(
        title="어떤 책",
        author="홍길동",
        raw_category="국내도서 > IT > 프로그래밍",
    )
    res1 = await service.classify_genre(req1)
    assert res1.genre == StandardGenre.IT_COMPUTER
    assert res1.confidence == 1.0

    # 2. 제목 기반 분류
    req2 = BookClassificationRequest(
        title="삼국지 역사 기행",
        author="나관중",
    )
    res2 = await service.classify_genre(req2)
    assert res2.genre == StandardGenre.HISTORY

    # 3. 매칭 없는 경우 ETC
    req3 = BookClassificationRequest(title="xyz 123 abc")
    res3 = await service.classify_genre(req3)
    assert res3.genre == StandardGenre.ETC


@pytest.mark.asyncio
async def test_genre_classifier_service_bedrock_mode(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """Bedrock 모드에서 Strands Agent 호출 및 결과 파싱이 정상 동작하는지 검증한다."""
    mock_agent_instance = MagicMock()
    mock_agent_result = MagicMock()
    mock_agent_result.message = {"content": [{"text": '{"genre": "과학", "confidence": 0.92}'}]}
    mock_agent_instance.invoke_async = AsyncMock(return_value=mock_agent_result)

    mocker.patch(
        "discovery.application.genre_classifier_service.Agent",
        return_value=mock_agent_instance,
    )
    mocker.patch(
        "discovery.application.genre_classifier_service.BedrockModel",
    )

    service = GenreClassifierService(settings=bedrock_settings)
    req = BookClassificationRequest(
        title="코스모스",
        author="칼 세이건",
        raw_category="자연과학",
    )
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.SCIENCE
    assert res.confidence == 0.92


@pytest.mark.asyncio
async def test_genre_classifier_service_exception_fallback(
    bedrock_settings: Settings, mocker: MockerFixture
) -> None:
    """Bedrock 호출 중 예외가 발생해도 500 에러 대신 '기타'와 0.0 신뢰도를 반환하는지 검증한다."""
    mocker.patch(
        "discovery.application.genre_classifier_service.Agent",
        side_effect=RuntimeError("AWS Connection Failed"),
    )

    service = GenreClassifierService(settings=bedrock_settings)
    req = BookClassificationRequest(title="코스모스")
    res = await service.classify_genre(req)

    assert res.genre == StandardGenre.ETC
    assert res.confidence == 0.0
