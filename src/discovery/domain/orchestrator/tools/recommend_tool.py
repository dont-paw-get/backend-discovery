"""추천 에이전트를 오케스트레이터의 도구로 감싸는 로컬 도구."""

import asyncio
import re
import time
from typing import Any

from strands import tool

from discovery.api.schemas.genre import (
    BookClassificationRequest,
    BookClassificationResponse,
    StandardGenre,
)
from discovery.application.genre_classifier_service import GenreClassifierService
from discovery.core.config import Settings
from discovery.core.observability import log_agent_metrics
from discovery.domain.librarian.agent import create_librarian_agent
from discovery.domain.librarian.post_processor import (
    RecommendedBookFields,
    extract_text_from_message,
    parse_recommended_books_from_markdown,
    truncate_books_by_count,
)
from discovery.domain.orchestrator.tools.book_metadata_client import BookMetadataClient
from discovery.infrastructure.search.book_search_tool import BookSearchTool


class RecommendBooksTool:
    """도서 추천 에이전트를 오케스트레이터의 Agent-as-a-Tool로 실행하는 도구."""

    def __init__(
        self,
        book_search_tool: BookSearchTool,
        settings: Settings,
        book_metadata_client: BookMetadataClient | None = None,
        genre_classifier_service: GenreClassifierService | None = None,
        boto_session: Any = None,
    ) -> None:
        self._book_search_tool = book_search_tool
        self._settings = settings
        self._book_metadata_client = book_metadata_client
        self._genre_classifier_service = genre_classifier_service
        self._boto_session = boto_session

    async def recommend(
        self,
        query: str,
        count: int = 2,
        librarian_id: str | None = None,
        session_id: str | None = None,
        auth_token: str | None = None,
    ) -> str:
        """추천 에이전트를 생성하여 도서 추천 및 웹 검색을 수행하고 결과를 반환한다.

        - `count`는 1~5 범위로 clamp하여 생성량을 유도한다.
        - 반환 지점에서 `truncate_books_by_count` 순수 함수를 호출하여
          초과분을 결정론적으로 잘라낸다.
        - CLIAR-237 후속: 각 도서 블록에서 파싱한 제목/저자로 `backend-book`의
          제목·저자 교집합 검색 API(`GET /api/v1/books/search/by-title-author`)를
          호출하여 정확한 페이지수를 검증하고 마크다운의 `({페이지수}쪽)` 표기를
          덮어쓴다. 검증 실패(검색 결과 없음, 네트워크 오류 등) 시 LLM 생성값을
          그대로 유지한다(graceful degradation, 재시도 없음).
        - 하위 에이전트 실행 메트릭(Strands metrics 및 소요시간)을 수집하여 로깅한다.
        """
        start_time = time.perf_counter()
        clamped_count = max(1, min(count, 5))
        agent_creation_start = time.perf_counter()
        agent = create_librarian_agent(
            model_id=self._settings.librarian_model_id,
            region_name=self._settings.aws_region,
            boto_session=self._boto_session,
            librarian_id=librarian_id,
            tools=[self._book_search_tool.as_tool()],
            enable_prompt_caching=self._settings.enable_prompt_caching,
        )
        agent_creation_ms = round((time.perf_counter() - agent_creation_start) * 1000, 2)

        invoke_start = time.perf_counter()
        prompt = (
            f"{query}\n\n"
            f"[요청] 반드시 {clamped_count}권의 도서만 추천해주세요. "
            "search_books 도구는 정확히 1회만 호출하고, 그 한 번의 검색어로 "
            f"{clamped_count}권 분량의 후보와 서지 정보를 한꺼번에 확보하세요. "
            "인사말이나 서두/맺음 멘트는 일절 쓰지 말고, "
            "오직 '### 📖 {도서 제목}' 카드 규격만 바로 출력하세요."
        )
        event_timeline: list[tuple[float, str]] = []

        def _on_event(**kwargs: Any) -> None:
            elapsed_ms = round((time.perf_counter() - invoke_start) * 1000, 2)
            # 이벤트 종류를 유추할 수 있는 키만 라벨로 남긴다(본문/프롬프트는 기록하지
            # 않음 — 개인정보 및 페이로드 크기 방어, AGENTS.md 로깅 정책과 일치).
            label = next(iter(kwargs.keys()), "unknown")
            event_timeline.append((elapsed_ms, label))

        agent.callback_handler = _on_event
        result = await agent.invoke_async(prompt=prompt)
        invoke_ms = round((time.perf_counter() - invoke_start) * 1000, 2)
        gap_ms, gap_after_label = _largest_event_gap_ms(event_timeline, invoke_ms)

        raw_text = extract_text_from_message(result.message)
        truncated_text = truncate_books_by_count(raw_text, count=clamped_count)

        verify_start = time.perf_counter()
        processed_text = await self._verify_page_counts(truncated_text, auth_token=auth_token)
        verify_ms = round((time.perf_counter() - verify_start) * 1000, 2)

        duration_ms = round((time.perf_counter() - start_time) * 1000, 2)
        metrics_summary = (
            result.metrics.get_summary()
            if hasattr(result, "metrics") and result.metrics
            else None
        )
        log_agent_metrics(
            phase="recommend_agent",
            session_id=session_id or "unknown",
            librarian_id=librarian_id,
            mode="sync",
            message_length=len(query),
            metrics_summary=metrics_summary,
            direct_metrics={
                "total_duration_ms": duration_ms,
                "agent_creation_ms": agent_creation_ms,
                "agent_invoke_ms": invoke_ms,
                "verify_page_counts_ms": verify_ms,
                "largest_event_gap_ms": gap_ms,
                "largest_event_gap_after": gap_after_label,
                "event_count": len(event_timeline),
            },
        )
        return processed_text

    async def _verify_page_counts(self, markdown: str, auth_token: str | None = None) -> str:
        """마크다운의 각 `### 📖` 도서 블록에서 제목/저자를 추출해 페이지수와 장르를 검증하고,
        검증된 값으로 `({페이지수}쪽)` 표기 및 `- **장르**:` 라인을 덮어쓴다.

        `book_metadata_client`가 배선되지 않았거나 제목/저자를 파싱할 수 있는 블록이
        하나도 없으면 원본을 그대로 반환한다. `auth_token`은 backend-book 서지 조회
        API가 요구하는 사용자 인증 토큰으로, `fetch_isbn_and_pages`까지 패스스루된다.

        CLIAR-282: LLM이 마크다운 형식(특히 `- **장르**:` 라인)을 멀티턴 대화 후반부에서
        자주 빼먹는 것이 dev 실측으로 확인되어(장르 칩이 프론트에 안 뜨는 버그), 장르가
        비어있는(`NONE`) 도서는 backend-book에서 얻은 ISBN으로 `GenreClassifierService`
        (기존 `POST /api/v1/classify-genre` API의 서비스 레이어, ISBN 기반 LLM 분류)를
        재호출해 결정론적으로 보강한다. `genre_classifier_service`가 배선되지 않았거나
        ISBN을 못 구했거나 분류 결과가 `NONE`이면 원본을 그대로 둔다(추가 손해 없음).

        CLIAR-282 병렬화: 책마다 `_resolve_isbn_pages_and_genre`가 "ISBN 확보(1단계)" →
        "페이지수 2단계 조회"와 "장르 분류 LLM 호출"을 `asyncio.gather`로 동시 실행한다
        (두 호출은 ISBN만 공유하고 서로 결과에 의존하지 않아 안전하게 병렬화된다).
        이 책 단위 처리 자체도 전체 도서 목록에 대해 `asyncio.gather`로 동시 실행되어,
        dev 실측상 순차(권당 3~6초) 대비 최대 절반까지 후처리 구간을 단축한다.
        """
        if self._book_metadata_client is None:
            return markdown

        parsed = parse_recommended_books_from_markdown(markdown)
        author_by_title: dict[str, str] = {
            b["title"]: author for b in parsed if (author := b.get("author"))
        }
        if not author_by_title:
            return markdown

        genre_by_title_hint = {b["title"]: b["genre"] for b in parsed}
        titles = list(author_by_title.keys())

        resolved = await asyncio.gather(
            *(
                self._resolve_isbn_pages_and_genre(
                    title=t,
                    author=author_by_title[t],
                    needs_genre=genre_by_title_hint.get(t) == StandardGenre.NONE,
                    auth_token=auth_token,
                )
                for t in titles
            )
        )

        for title, (verified_page, genre_response) in zip(titles, resolved, strict=True):
            if verified_page:
                markdown = _replace_page_count_for_title(markdown, title, verified_page)
            if genre_response is not None and genre_response.genre != StandardGenre.NONE:
                markdown = _upsert_genre_for_title(markdown, title, genre_response.genre.value)

        return markdown

    async def _resolve_isbn_pages_and_genre(
        self,
        title: str,
        author: str,
        needs_genre: bool,
        auth_token: str | None,
    ) -> tuple[int | None, BookClassificationResponse | None]:
        """한 도서의 (검증된 페이지수, 장르 분류 결과)를 확보한다.

        `BookMetadataCache`에 히트하면 캐시된 (ISBN, 페이지수)를 그대로 쓰고 이 책에
        대한 HTTP 호출은 발생하지 않는다(장르는 캐시되지 않으므로 `needs_genre`이면
        여전히 LLM 분류를 수행한다). 캐시 미스이면 1단계(`by-title-author`)로 ISBN을
        먼저 확보한 뒤, 서로 의존성이 없는 "페이지수 2단계 조회"와 "장르 분류
        LLM 호출"을 `asyncio.gather`로 동시 실행한다.
        """
        client = self._book_metadata_client
        assert client is not None  # 호출부에서 이미 None 체크됨

        cached = await client.get_cached_isbn_and_pages(title, author)
        if cached is not None:
            isbn, pages = cached
        else:
            isbn = await client.fetch_isbn_only(title, author, auth_token=auth_token)

        genre_task = (
            self._genre_classifier_service.classify_genre(
                BookClassificationRequest(isbn=isbn or "")
            )
            if needs_genre and isbn and self._genre_classifier_service is not None
            else None
        )

        if cached is None and isbn is not None:
            pages_task = client.fetch_total_pages(isbn, auth_token=auth_token)
            if genre_task is not None:
                pages, genre_response = await asyncio.gather(pages_task, genre_task)
            else:
                pages = await pages_task
                genre_response = None
            await client.cache_isbn_and_pages(title, author, isbn, pages)
        elif cached is None:
            pages = None
            genre_response = await genre_task if genre_task is not None else None
        else:
            genre_response = await genre_task if genre_task is not None else None

        return (pages, genre_response)

    async def _backfill_missing_genres(
        self,
        markdown: str,
        parsed: list[RecommendedBookFields],
        isbn_and_pages_by_title: dict[str, tuple[str | None, int | None]],
    ) -> str:
        """장르가 `NONE`인 도서 블록에 `GenreClassifierService`로 결정론적 장르를 보강한다.

        CLIAR-282 병렬화 이후에는 `_verify_page_counts`가 `_resolve_isbn_pages_and_genre`로
        장르 분류까지 함께 병렬 처리하므로 실제 호출 경로에서는 쓰이지 않는다. 다만
        기존 계약(순차 폴백 경로)을 참조하는 테스트/외부 코드가 있을 수 있어 메서드
        자체는 하위 호환으로 유지한다.
        """
        if self._genre_classifier_service is None:
            return markdown

        titles_needing_genre = [
            book["title"]
            for book in parsed
            if book["genre"] == StandardGenre.NONE
            and isbn_and_pages_by_title.get(book["title"], (None, None))[0]
        ]
        if not titles_needing_genre:
            return markdown

        classified = await asyncio.gather(
            *(
                self._genre_classifier_service.classify_genre(
                    BookClassificationRequest(
                        isbn=isbn_and_pages_by_title[title][0] or ""
                    )
                )
                for title in titles_needing_genre
            )
        )
        for title, response in zip(titles_needing_genre, classified, strict=True):
            if response.genre != StandardGenre.NONE:
                markdown = _upsert_genre_for_title(markdown, title, response.genre.value)
        return markdown

    def as_tool(
        self,
        librarian_id: str | None = None,
        session_id: str | None = None,
        auth_token: str | None = None,
    ) -> Any:
        """Strands 오케스트레이터 에이전트에 등록할 @tool 함수를 반환한다.

        `auth_token`은 서비스 레이어에서 클로저로 주입되어(LLM 인자로 노출하지 않음),
        페이지수 검증 시 backend-book 서지 조회 API 호출에 사용된다.
        """

        @tool(name="recommend_books")
        async def recommend_books_tool(query: str, count: int = 2) -> str:
            """사용자의 상황, 관심사, 장르, 요청 권수에 맞는 도서를 웹 검색 기반으로 추천하고
            상세히 안내합니다.

            Args:
                query: 도서 추천을 위한 구체적인 검색어 또는 사용자의 요구사항
                    (예: '비 오는 날 읽기 좋은 힐링 소설', 'SF 입문작').
                count: 추천할 도서 권수 (기본값: 2, 1~5권 범위).
            """
            return await self.recommend(
                query=query,
                count=count,
                librarian_id=librarian_id,
                session_id=session_id,
                auth_token=auth_token,
            )

        return recommend_books_tool


def _largest_event_gap_ms(
    event_timeline: list[tuple[float, str]], total_invoke_ms: float
) -> tuple[float, str]:
    """CLIAR-282 진단: Strands 콜백 이벤트 사이의 가장 큰 시간 간극과, 그 간극이
    어느 이벤트 뒤에서 발생했는지 반환한다.

    `strands_metrics.total_duration`(이벤트 루프 사이클 시간)과 실제
    `agent_invoke_ms`(wall-clock) 사이에 설명되지 않는 간극이 반복적으로 관측되어
    (dev 실측, 2026-09-04), 콜백 이벤트 사이 간격을 직접 재서 "어느 이벤트 이후"에
    시간이 새는지 좁히기 위한 진단 계측이다. 이벤트가 없으면(콜백이 전혀 안 불린
    경우 등) 첫 이벤트 이전 구간 전체를 간극으로 본다.

    Args:
        event_timeline: `(경과 시간(ms), 이벤트 종류 라벨)` 튜플 목록, 발생 순서대로.
        total_invoke_ms: `agent.invoke_async` 전체 소요시간(ms). 마지막 이벤트 이후
            결과 조립까지 남는 시간을 재기 위해 종료 시각으로 사용한다.

    Returns:
        `(가장 큰 간극(ms), 그 간극 직전 이벤트 라벨)`. 이벤트가 없으면
        `(total_invoke_ms, "no_events")`.
    """
    if not event_timeline:
        return (total_invoke_ms, "no_events")

    boundaries = [0.0, *[t for t, _ in event_timeline], total_invoke_ms]
    labels = ["start", *[label for _, label in event_timeline]]

    max_gap = 0.0
    max_gap_after = labels[0]
    for i in range(1, len(boundaries)):
        gap = round(boundaries[i] - boundaries[i - 1], 2)
        if gap > max_gap:
            max_gap = gap
            max_gap_after = labels[i - 1]
    return (max_gap, max_gap_after)


def _replace_page_count_for_title(markdown: str, title: str, verified_page: int) -> str:
    """지정된 도서 제목의 저자 줄에 있는 `({N}쪽)` 표기를 검증된 페이지수로 교체한다.

    저자 줄에 쪽수 표기가 없으면(LLM이 생략했거나 근사치 표현을 프롬프트 지침에 따라
    쓰지 않은 경우) 새로 추가한다.
    """
    block_pattern = re.compile(
        r"(### 📖\s*" + re.escape(title) + r"\s*\n-\s*\*\*저자\*\*:\s*)(.+?)(\s*\n)"
    )

    def _replace(match: re.Match[str]) -> str:
        prefix, author_segment, suffix = match.group(1), match.group(2), match.group(3)
        # 기존 "(N쪽)" 또는 "(약 N쪽)" 등 근사치 표현을 제거하고 검증된 값으로 교체.
        author_only = re.sub(r"\s*\([^)]*쪽\)\s*$", "", author_segment).strip()
        return f"{prefix}{author_only} ({verified_page}쪽){suffix}"

    return block_pattern.sub(_replace, markdown, count=1)


def _upsert_genre_for_title(markdown: str, title: str, genre_value: str) -> str:
    """지정된 도서 블록에 `- **장르**: {genre_value}` 라인을 삽입하거나 교체한다.

    CLIAR-282: LLM이 마크다운 형식에서 `- **장르**:` 라인 자체를 통째로 빼먹는 경우
    (dev 실측 확인)가 있어, 저자 줄 뒤에 라인이 없으면 새로 추가하고 있으면 값만
    교체한다. 도서 블록의 끝(다음 `### 📖` 헤더 시작 지점 또는 텍스트 끝)을 기준으로
    삽입 위치를 정한다.
    """
    block_start_pattern = re.compile(r"(### 📖\s*" + re.escape(title) + r"\s*\n)")
    start_match = block_start_pattern.search(markdown)
    if not start_match:
        return markdown

    block_start = start_match.end()
    next_header_match = re.search(r"\n(?=### 📖)", markdown[block_start:])
    block_end = block_start + next_header_match.start() if next_header_match else len(markdown)
    block = markdown[block_start:block_end]

    genre_line_pattern = re.compile(r"-\s*\*\*장르\*\*:\s*(.+?)\s*$", re.MULTILINE)
    if genre_line_pattern.search(block):
        new_block = genre_line_pattern.sub(f"- **장르**: {genre_value}", block, count=1)
    else:
        new_block = block.rstrip("\n") + f"\n- **장르**: {genre_value}\n"

    return markdown[:block_start] + new_block + markdown[block_end:]
