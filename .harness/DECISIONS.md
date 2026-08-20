# DECISIONS — backend-discovery

최신 결정이 표 최상단에 온다 (append-only).

| 날짜 | 결정 | 이유 |
| --- | --- | --- |
| 2026-08-21 | `AGENTS.md`에 "Git 작업 정책" 섹션 추가(커밋은 Task 단위+`[CLIAR-XX]` 태그 필수, push/merge는 사용자 승인 없이 금지, push 전 변경 파일·diff 요약 선제시) + `.pre-commit-config.yaml`로 ruff/mypy/커밋 메시지 형식 훅 도입 | CLIAR-40부터 커밋 단위를 세분화하고 push/merge 실수를 원천 방지하기 위해 명문화가 필요했다. pre-commit 훅으로 커밋 시점에 정적 분석과 메시지 형식을 자동 검증해 사람이 매번 수동으로 챙기지 않게 한다. push/merge 승인 정책은 훅이 아니라 에이전트 워크플로우 규칙이므로 pre-commit 범위에는 포함하지 않는다. |
| 2026-08-21 | AWS 계정 확보 이후에도 Bedrock 실연동 스위치는 기존 `LLM_PROVIDER=mock\|bedrock`(`core/config.py`)를 그대로 사용하고, 별도 `USE_REAL_BEDROCK` 같은 boolean 플래그는 추가하지 않는다. 기본값은 `mock` 유지 | `LLM_PROVIDER`가 이미 구현체 선택이라는 동일한 역할을 하고 있어, 별도 스위치를 추가하면 두 값이 서로 어긋날 위험(예: `LLM_PROVIDER=mock`인데 `USE_REAL_BEDROCK=true`)이 생긴다. 하나의 신뢰 가능한 소스(single source of truth)를 유지한다. |
| 2026-08-20 | `color_tags` 필드 최종 제거 | `mood_tags`/`genre_tags` 제거 결정과 함께 처리됐어야 하나 누락되어 있었음. 확인 결과 `color_tags`는 애초에 사용자 요구사항으로 확정된 필드가 아니라, 초기 하네스 문서 세팅 시 README.md의 "무드·색상 다중 필터링" 서술을 참고해 임의로 `mood_tags`와 짝지어 추가한 필드였다. 처음부터 근거 없이 들어간 것이므로 뒤늦게 정정한다. |
| 2026-08-20 | GIN 인덱스 용도를 JSONB/배열 태그 필터링에서 `description + category` 결합 텍스트의 `tsvector` 전문검색(Full-Text Search)으로 전환. 하이브리드(벡터+키워드) 검색은 파라미터로 옵션화하고 기본값은 벡터 단독 검색으로 시작 | `mood_tags`/`genre_tags`를 만들지 않기로 하면서 태그 배열에 대한 GIN 사용 목적이 사라졌다. 대신 `search_vector`(tsvector) 컬럼에 GIN을 걸어 키워드 검색 인프라로 재활용한다. 하이브리드 검색의 실질적 효과가 검증되지 않았으므로 우선 옵션으로만 구현하고, 실사용 로그가 쌓이면 A/B로 벡터 단독 대비 개선 여부를 검증한 뒤 기본값 전환을 재검토한다. |
| 2026-08-20 | `mood_tags` 컬럼 제거, `genre_tags` 컬럼 신설하지 않음. `category`는 파싱 없이 원본 TEXT로 저장하고 임베딩 대상 텍스트에 포함 | Basic API가 보내는 카테고리 데이터가 아직 무드/장르 단위로 정규화되어 있지 않아, 지금 태그 컬럼을 만들면 실제 값 없이 스키마만 앞서가는 추측성 설계가 된다. 원본 텍스트를 그대로 저장하고 임베딩에 포함시키면 RAG 검색 품질에는 기여하면서 정규화 비용은 나중(Basic API 쪽 데이터가 안정된 후)으로 미룰 수 있다. |
| 2026-08-19 | `AGENTS.md`의 origin 주소를 `https://github.com/dont-paw-get/backend-discovery.git`로 정정 | 기존 값이 `backend-book.git`이었다. AGENTS.md가 backend-book 저장소에서 파생되며 남은 값으로, 이 저장소 기준과 불일치해 브랜치·PR 안내가 잘못된 원격을 가리킬 위험이 있었다. |
| 2026-08-19 | 의존성 관리는 `pyproject.toml` + `uv.lock` (uv) 채택, `requirements.txt` 미사용 | AGENTS.md "기술 스택·패키지 구조 변경" 항목이 파이썬 의존성 파일로 `pyproject.toml`과 lock 파일을 지정한다. ruff·mypy·pytest 설정을 한 파일로 모을 수 있어 설정 산재를 막고, uv는 lock 재현성과 설치 속도가 유리하다. |
| 2026-08-19 | `/internal/*` 라우터는 공유 시크릿 헤더(`X-Internal-Token`) 검증을 요구 | 서비스 간 전용 엔드포인트를 무인증 노출하면 외부에서 읽기 모델을 임의 조작할 수 있다. 값은 `.env`로 주입한다. 인프라 확정 후 mTLS/네트워크 격리로 대체할지 재검토한다. |
| 2026-08-19 | 임베딩 차원 1536 결정 | Titan Embed Text v1 가정. 추후 AWS 연동 시 사용할 모델에 따라 마이그레이션 및 재검토 필요. |
