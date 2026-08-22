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

ENV UV_NO_SYNC=1

EXPOSE 8000

CMD ["uv", "run", "--no-dev", "uvicorn", "discovery.main:app", "--host", "0.0.0.0", "--port", "8000"]
