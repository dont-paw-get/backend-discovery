"""CLIAR-215 Task 1: QA 46건 실측 러너.

`chatbot_qa_testv2.csv`(46개 QA 케이스)를 읽어 로컬에서 기동 중인
`/api/v1/chat`(stream=False)에 순차 호출하고, 질문·응답·소요시간·HTTP 상태코드를
`scripts/qa_results/`에 JSON Lines로 덤프한다.

사전 준비:
    1. Redis 로컬 기동: `docker compose up -d redis`
    2. 서버 기동: `uv run uvicorn discovery.main:app --reload --port 8001`
       (`.env`의 `LIBRARIAN_AGENT_URL`, `LLM_PROVIDER` 등은 실제 호출 대상에 맞게 설정)

사용법:
    uv run python scripts/qa_runner.py
    uv run python scripts/qa_runner.py --base-url http://localhost:8001 --auth-token "Bearer xxx"

주의:
    - 이 러너는 Bedrock을 실제로 호출한다(LLM_PROVIDER=bedrock 시 비용 발생).
    - 개인정보 방어 원칙에 따라 결과 파일에 사용자 발화 원문(질문 컬럼)은 CSV 자체에
      이미 포함되어 있으므로 그대로 기록하되, 실행 로그를 커밋 대상에 포함하지 않는다
      (`.gitignore`에 `scripts/qa_results/` 추가됨).
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import httpx

CSV_PATH = Path(__file__).resolve().parent / "data" / "chatbot_qa_testv2.csv"
RESULTS_DIR = Path(__file__).resolve().parent / "qa_results"

# 5턴 이상 연속 대화, 세션 격리 등 여러 요청이 하나의 시나리오를 구성하는 카테고리.
# 이 카테고리는 CSV의 "질문" 컬럼 한 줄로 표현 불가하므로 별도 시나리오 함수로 처리하고,
# 기본 러너 루프에서는 스킵한다.
MULTI_TURN_CATEGORIES = {"세션 유지", "세션 격리", "개인화", "성능/속도", "반복 질문", "언어 전환"}

# CSV의 "질문" 컬럼이 실제 재현 가능한 입력이 아니라 시나리오 설명인 경우,
# 카테고리+질문 원문을 키로 하여 실제로 전송할 입력으로 치환한다.
QUESTION_OVERRIDES: dict[tuple[str, str], str] = {
    ("오탈자/비정상 입력", "(빈 메시지 전송)"): "",
    ("엣지 케이스", "숫자만 입력 (예: 12345)"): "12345",
    ("엣지 케이스", "이모지만 입력 (예: 😊📚)"): "😊📚",
    ("번역 검증", "일본 소설/만화 추천 유도 질문 (원제가 일본어인 도서 포함)"): (
        "진격의 거인이나 나루토 같은 일본 만화/소설 추천해줘"
    ),
}


def resolve_question(category: str, question: str) -> str:
    """시나리오 설명 문자열을 실제 전송 가능한 입력으로 치환한다."""
    return QUESTION_OVERRIDES.get((category, question), question)


@dataclass
class QACaseResult:
    index: int
    category: str
    question: str
    purpose: str
    priority: str
    session_id: str
    status_code: int | None
    response_message: str | None
    latency_ms: float
    error: str | None = None
    raw_question: str | None = None


def load_qa_cases() -> list[dict[str, str]]:
    """CSV를 읽어 QA 케이스 목록을 반환한다."""
    with CSV_PATH.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        return list(reader)


async def call_chat(
    client: httpx.AsyncClient,
    *,
    message: str,
    session_id: str,
    auth_token: str | None,
    latitude: float | None = None,
    longitude: float | None = None,
) -> tuple[int, dict[str, Any] | None, float]:
    """`/api/v1/chat`을 1회 호출하고 (status_code, json_body, latency_ms)를 반환한다."""
    headers = {}
    if auth_token:
        headers["Authorization"] = auth_token

    payload: dict[str, Any] = {"session_id": session_id, "message": message, "stream": False}
    if latitude is not None:
        payload["latitude"] = latitude
    if longitude is not None:
        payload["longitude"] = longitude

    start = time.perf_counter()
    try:
        resp = await client.post("/api/v1/chat", json=payload, headers=headers, timeout=60.0)
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        body: dict[str, Any] | None
        try:
            body = resp.json()
        except Exception:
            body = None
        return resp.status_code, body, latency_ms
    except Exception as e:
        latency_ms = round((time.perf_counter() - start) * 1000, 2)
        return -1, {"error": str(e)}, latency_ms


async def run_single_turn_cases(
    client: httpx.AsyncClient,
    cases: list[dict[str, str]],
    auth_token: str | None,
) -> list[QACaseResult]:
    """단발 질문 케이스(대부분의 카테고리)를 순차 실행한다.

    케이스마다 새 session_id(UUID)를 사용해 세션 간 오염을 방지한다.
    """
    results: list[QACaseResult] = []
    for idx, row in enumerate(cases, start=1):
        category = row["카테고리"]
        if category in MULTI_TURN_CATEGORIES:
            continue

        session_id = f"qa-{idx}-{uuid.uuid4().hex[:8]}"
        raw_question = row["질문"]
        question = resolve_question(category, raw_question)

        # signals-좌표이상값: 의도적으로 범위 밖 좌표 전달
        latitude = longitude = None
        if category == "signals-좌표이상값":
            latitude, longitude = 999.0, 999.0
        elif category == "signals-날씨반영":
            latitude, longitude = 37.5665, 126.9780

        status_code, body, latency_ms = await call_chat(
            client,
            message=question,
            session_id=session_id,
            auth_token=auth_token,
            latitude=latitude,
            longitude=longitude,
        )
        response_message = body.get("message") if isinstance(body, dict) else None
        error = body.get("error") if isinstance(body, dict) and "error" in body else None

        results.append(
            QACaseResult(
                index=idx,
                category=category,
                question=question,
                purpose=row["테스트_목적/기대_동작"],
                priority=row["우선순위"],
                session_id=session_id,
                status_code=status_code if status_code != -1 else None,
                response_message=response_message,
                latency_ms=latency_ms,
                error=error,
                raw_question=raw_question if raw_question != question else None,
            )
        )
    return results


async def run_auth_edge_cases(
    client: httpx.AsyncClient,
) -> list[QACaseResult]:
    """인증 카테고리의 두 하위 케이스(헤더 없음 / 위조 토큰)를 명시적으로 실행한다."""
    results: list[QACaseResult] = []

    # 1) Authorization 헤더 없이 호출 → 401 기대 (CLIAR-215 Task 2 구현 후)
    status_code, body, latency_ms = await call_chat(
        client, message="내 서재 책 알려줘", session_id=f"qa-auth-missing-{uuid.uuid4().hex[:8]}",
        auth_token=None,
    )
    results.append(
        QACaseResult(
            index=-1, category="인증-헤더없음", question="(Authorization 헤더 미전달)",
            purpose="401 등 인증 실패 응답이 정확히 오는지 확인", priority="1",
            session_id="-", status_code=status_code if status_code != -1 else None,
            response_message=body.get("message") if isinstance(body, dict) else None,
            latency_ms=latency_ms,
        )
    )

    # 2) 위조 토큰으로 호출 → discovery 자체 401은 기대하지 않음(Presence Check만 수행).
    #    backend-book 호출 시점의 401 전달 여부를 관찰한다.
    status_code, body, latency_ms = await call_chat(
        client, message="내 서재 책 알려줘", session_id=f"qa-auth-forged-{uuid.uuid4().hex[:8]}",
        auth_token="Bearer forged.invalid.token",
    )
    results.append(
        QACaseResult(
            index=-2, category="인증-위조토큰", question="(위조 JWT 전달)",
            purpose="인증 실패 처리 및 에러 메시지 적절성 확인", priority="1",
            session_id="-", status_code=status_code if status_code != -1 else None,
            response_message=body.get("message") if isinstance(body, dict) else None,
            latency_ms=latency_ms,
        )
    )
    return results


async def run_multi_turn_session_case(
    client: httpx.AsyncClient, auth_token: str | None
) -> QACaseResult:
    """세션 유지: 동일 session_id로 5턴 연속 대화."""
    session_id = f"qa-multiturn-{uuid.uuid4().hex[:8]}"
    turns = [
        "안녕하세요",
        "판타지 소설 좋아해요",
        "추천해줄 책 있어요?",
        "그중에 제일 짧은 건요?",
        "고마워요",
    ]
    last_latency = 0.0
    last_status: int | None = None
    last_message: str | None = None
    for turn in turns:
        status_code, body, latency_ms = await call_chat(
            client, message=turn, session_id=session_id, auth_token=auth_token
        )
        last_latency = latency_ms
        last_status = status_code if status_code != -1 else None
        last_message = body.get("message") if isinstance(body, dict) else None
    return QACaseResult(
        index=-3, category="세션 유지-5턴", question=" -> ".join(turns),
        purpose="Redis에 대화 기록이 순서대로 유지되는지 확인", priority="1",
        session_id=session_id, status_code=last_status, response_message=last_message,
        latency_ms=last_latency,
    )


async def run_session_isolation_case(
    client: httpx.AsyncClient, auth_token: str | None
) -> QACaseResult:
    """세션 격리: 서로 다른 두 session_id로 동시 대화 후 교차 오염 여부 확인."""
    session_a = f"qa-isolation-a-{uuid.uuid4().hex[:8]}"
    session_b = f"qa-isolation-b-{uuid.uuid4().hex[:8]}"

    await call_chat(
        client, message="저는 판타지를 좋아해요", session_id=session_a, auth_token=auth_token
    )
    await call_chat(
        client, message="저는 경영서를 좋아해요", session_id=session_b, auth_token=auth_token
    )

    status_code, body, latency_ms = await call_chat(
        client, message="아까 말한 제 취향이 뭐였죠?", session_id=session_a, auth_token=auth_token
    )
    return QACaseResult(
        index=-4,
        category="세션 격리",
        question="session_a 취향 재질문 (session_b와 교차 오염 여부)",
        purpose="한 세션의 대화 기록이 다른 세션에 노출되지 않는지 확인",
        priority="1",
        session_id=session_a, status_code=status_code if status_code != -1 else None,
        response_message=body.get("message") if isinstance(body, dict) else None,
        latency_ms=latency_ms,
    )


def write_results(results: list[QACaseResult], filename: str) -> Path:
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    out_path = RESULTS_DIR / filename
    with out_path.open("w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    return out_path


def print_summary(results: list[QACaseResult]) -> None:
    total = len(results)
    failed = [r for r in results if r.status_code is None or r.status_code >= 400 or r.error]
    print(f"\n총 {total}건 실행, 실패/에러 {len(failed)}건")
    if failed:
        print("--- 실패/에러 케이스 ---")
        for r in failed:
            print(
                f"  [{r.category}] {r.question[:40]!r} -> "
                f"status={r.status_code}, error={r.error}"
            )


async def main() -> None:
    parser = argparse.ArgumentParser(description="CLIAR-215 QA 46건 실측 러너")
    parser.add_argument("--base-url", default="http://localhost:8001")
    parser.add_argument("--auth-token", default=None, help="예: 'Bearer xxx'")
    parser.add_argument(
        "--skip-multi-turn", action="store_true", help="세션 유지/격리 등 다회 호출 시나리오 스킵"
    )
    args = parser.parse_args()

    cases = load_qa_cases()
    print(f"CSV에서 {len(cases)}건 로드")

    async with httpx.AsyncClient(base_url=args.base_url) as client:
        single_results = await run_single_turn_cases(client, cases, args.auth_token)
        auth_results = await run_auth_edge_cases(client)

        multi_results: list[QACaseResult] = []
        if not args.skip_multi_turn:
            multi_results.append(await run_multi_turn_session_case(client, args.auth_token))
            multi_results.append(await run_session_isolation_case(client, args.auth_token))

    all_results = single_results + auth_results + multi_results
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    out_path = write_results(all_results, f"qa_run_{timestamp}.jsonl")
    print(f"결과 저장: {out_path}")
    print_summary(all_results)


if __name__ == "__main__":
    asyncio.run(main())
