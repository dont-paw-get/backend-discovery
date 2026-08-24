# syntax=docker/dockerfile:1
FROM python:3.12-slim

# uv 바이너리를 공식 배포 이미지에서 그대로 복사 (uv 자체 설치 없이 사용)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1
# 의존성 정의만 먼저 복사해 소스 변경 시 레이어 캐시를 재사용한다.
# README.md는 pyproject.toml의 readme 필드가 참조하므로 빌드 메타데이터 검증에 필요하다.
COPY pyproject.toml uv.lock README.md ./

# uv.lock 기반 재현 가능한 설치 (requirements.txt/pip install 미사용).
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src

RUN uv sync --frozen --no-dev

EXPOSE 8000

# uv run 은 실행 시점에 캐시 디렉토리(/.cache/uv)를 만들려고 시도하는데,
# readOnlyRootFilesystem 환경에서는 이게 실패한다. 빌드 시 만들어진
# .venv 의 uvicorn 을 직접 실행해 런타임에 uv 를 거치지 않도록 한다.
CMD ["/app/.venv/bin/uvicorn", "discovery.main:app", "--host", "0.0.0.0", "--port", "8000"]
