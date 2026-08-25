"""애플리케이션 설정. 모든 접속 정보는 여기(.env 경유)로만 읽는다.

AGENTS.md DB 정책: 코드/설정에 접속 정보 기본값을 하드코딩하지 않는다.

Bedrock 모델 가용성 (2026-08-21, 교육 계정 기준 확인): Claude Haiku 4.5/Claude
Sonnet 4 이상 최신 모델은 `kosa-edu-region-pol`로 전 리전 차단됨. Claude 3 Haiku,
Claude 3.5 Sonnet은 실제 호출 가능(콘솔+CLI 확인). 상세는 `.harness/BACKLOG.md` 참고.
"""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """환경 변수 기반 설정. 필드는 .env.example과 1:1로 대응한다.

    Bedrock 모델 ID는 용도별로 분리한다(단일 필드로 전체를 통일하지 않음). 지금은
    추천 에이전트 하나만 있어 `librarian_model_id`뿐이지만, 나중에 특정 기능만
    다른 모델(예: Claude 3.5 Sonnet)로 바꿀 때 해당 필드만 환경변수로 교체하면
    되도록 확장 지점을 미리 둔다.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    redis_url: str
    llm_provider: str = "mock"
    internal_api_token: str
    aws_region: str | None = None
    chat_history_max_turns: int = 20
    chat_session_ttl_seconds: int = 3600
    # 추천 에이전트 전용 모델. 기본값 Claude 3 Haiku
    # (`anthropic.claude-3-haiku-20240307-v1:0`) — 교육 계정에서 실제 호출 가능
    # 확인된 모델. 특정 기능만 더 강한 모델(Claude 3.5 Sonnet 등)로 바꾸려면
    # `LIBRARIAN_MODEL_ID` 환경변수만 교체한다(다른 용도의 모델 설정에 영향 없음).
    librarian_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    orchestrator_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    genre_classifier_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    librarian_agent_url: str | None = None
    tavily_api_key: str
    tavily_cache_ttl_seconds: int = 86400
    tavily_monthly_credit_limit: int = 900


@lru_cache
def get_settings() -> Settings:
    """설정 인스턴스를 프로세스 생애주기 동안 캐시한다."""
    return Settings()
