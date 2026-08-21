"""애플리케이션 설정. 모든 접속 정보는 여기(.env 경유)로만 읽는다.

AGENTS.md DB 정책: 코드/설정에 접속 정보 기본값을 하드코딩하지 않는다.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정. 필드는 .env.example과 1:1로 대응한다."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str
    redis_url: str
    llm_provider: str = "mock"
    internal_api_token: str
    aws_region: str | None = None
    chat_history_max_turns: int = 20
    chat_session_ttl_seconds: int = 3600


@lru_cache
def get_settings() -> Settings:
    """설정 인스턴스를 프로세스 생애주기 동안 캐시한다."""
    return Settings()
