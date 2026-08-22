#!/usr/bin/env python3
"""커밋 메시지 제목에 `[CLIAR-XX]` 티켓 태그가 포함되어 있는지 검증한다.

.github/CONTRIBUTING.md 컨벤션: <타입>[scope]: [CLIAR-000] <제목>
pre-commit의 commit-msg 훅에서 호출되며, 첫 번째 인자로 커밋 메시지 파일 경로를 받는다.
"""

import re
import sys

TICKET_PATTERN = re.compile(r"\[CLIAR-\d+\]")


def main() -> int:
    if len(sys.argv) < 2:
        print("commit message file path가 전달되지 않았습니다.", file=sys.stderr)
        return 1

    commit_msg_path = sys.argv[1]
    with open(commit_msg_path, encoding="utf-8") as f:
        first_line = f.readline().strip()

    if not TICKET_PATTERN.search(first_line):
        print(
            "커밋 메시지 제목에 [CLIAR-XX] 형식의 티켓 번호가 없습니다.\n"
            f"  현재 제목: {first_line}\n"
            "  예: feat: [CLIAR-40] pgvector 도서 모델 추가",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
