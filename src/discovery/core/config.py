"""애플리케이션 설정. 모든 접속 정보는 여기(.env 경유)로만 읽는다.

AGENTS.md DB 정책: 코드/설정에 접속 정보 기본값을 하드코딩하지 않는다.

Bedrock 모델 가용성 (2026-09-04, 교육 계정 기준 재확인): 2026-08-21 시점에는 Claude
Haiku 4.5/Sonnet 4 이상이 `kosa-edu-region-pol`로 전 리전 차단되어 있었으나, 그 사이
계정 권한이 풀려 Sonnet 5(CLIAR-189)와 Haiku 4.5(CLIAR-278) 모두 글로벌 크로스리전
프로필로 실제 호출 가능함을 `aws bedrock-runtime converse` 직접 호출로 확인했다.
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
    # Claude Sonnet 5 글로벌 프로파일 사용 시 us-east-1 필수
    aws_region: str | None = "us-east-1"
    chat_history_max_turns: int = 20
    chat_session_ttl_seconds: int = 3600
    # 추천 에이전트 및 오케스트레이터 모델: Claude Haiku 4.5 글로벌 크로스리전 프로필
    # (CLIAR-278, 2026-09-04). Sonnet 5(`global.anthropic.claude-sonnet-5`)보다 레이턴시가
    # 짧은 경량 모델로 교체. 모델 ID는 AWS 공식 문서 기준
    # (model-card-anthropic-claude-haiku-4-5). 이 계정에서 `aws bedrock-runtime converse`로
    # 직접 실호출해 정상 응답을 확인했다(latencyMs: 809) — `.harness/BACKLOG.md`의 "Haiku 4.5는
    # kosa-edu-region-pol로 전 리전 차단" 기록은 그 사이 계정 권한이 풀려 더 이상 사실이 아니다.
    librarian_model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    orchestrator_model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    # [Sonnet 5로 롤백 시]
    # librarian_model_id: str = "global.anthropic.claude-sonnet-5"
    # orchestrator_model_id: str = "global.anthropic.claude-sonnet-5"
    # [서울 리전 초저지연 fallback 옵션 (TTFT ~600ms)]
    # aws_region: str | None = "ap-northeast-2"
    # librarian_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    # orchestrator_model_id: str = "anthropic.claude-3-5-sonnet-20240620-v1:0"
    # CLIAR-282: 구형 Claude 3 Haiku(2024-03)에서 Haiku 4.5 글로벌 프로필로 교체.
    # 추천 도서 장르 결정론적 보강(_backfill_missing_genres)이 이 모델을 추가 호출하며
    # verify_page_counts_ms를 늘렸는데(2.8초→5.3초 dev 실측), 장르 분류 자체를
    # 빠른 모델로 바꿔 그 증가분을 상쇄한다.
    genre_classifier_model_id: str = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
    librarian_agent_url: str | None = None
    librarian_default_id: str = "cat"
    librarian_http_timeout_seconds: float = 20.0
    initial_meta_timeout_seconds: float = 1.5
    enable_prompt_caching: bool = False
    # CLIAR-276: 기존 Prometheus/Grafana/Loki 관측 스택과 완전히 분리된 CloudWatch 커스텀
    # 메트릭(비용/토큰/캐시 히트율) 발행 스위치. 기본 False — 켜기 전엔 core/cloudwatch_metrics.py
    # 코드 경로 자체가 실행되지 않는다(`enable_prompt_caching` 선례와 동일한 안전 기본값 패턴).
    enable_cloudwatch_metrics: bool = False
    library_api_url: str = (
        "http://k8s-dpybbook-backendb-d17a725d36-1113312703.ap-northeast-2.elb.amazonaws.com"
    )
    library_http_timeout_seconds: float = 10.0
    # CLIAR-237: 추천 도서 페이지수를 알라딘 실조회로 검증하기 위한 backend-book 서지 조회
    # 엔드포인트. backend-book이 library_api_url과 동일 서비스이므로 기본값을 재사용한다.
    book_metadata_api_url: str = (
        "http://k8s-dpybbook-backendb-d17a725d36-1113312703.ap-northeast-2.elb.amazonaws.com"
    )
    book_metadata_timeout_seconds: float = 3.0
    tavily_api_key: str
    tavily_cache_ttl_seconds: int = 86400
    tavily_monthly_credit_limit: int = 900
    cors_allowed_origins: str = "http://localhost:3000"


@lru_cache
def get_settings() -> Settings:
    """설정 인스턴스를 프로세스 생애주기 동안 캐시한다."""
    return Settings()
