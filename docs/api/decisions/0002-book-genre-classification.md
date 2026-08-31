# ADR 0002: ERD 및 backend-book 표준 장르 체계(genre_type) 기반 도서 장르 분류 API 신설

- **상태**: 승인됨 (Accepted)
- **날짜**: 2026-08-25
- **티켓**: [CLIAR-103]

## 맥락 및 배경
- OCR 서비스 또는 외부 도서 API(알라딘 등)에서 도서를 등록할 때 수집되는 도서 제목, 저자, 원본 카테고리(`raw_category`)는 플랫폼마다 체계가 상이하고 비정형화되어 있다.
- DPYB 서비스의 DB(ERD 및 `backend-book`)에는 16개의 표준 장르 체계(`genre_type`: `SCIENCE_FICTION`, `FANTASY`, `ROMANCE`, `MYSTERY_THRILLER`, `LITERARY_FICTION`, `ESSAY`, `POETRY_DRAMA`, `HUMANITIES`, `HISTORY`, `BUSINESS_ECONOMICS`, `SELF_HELP`, `SCIENCE`, `ARTS`, `RELIGION`, `COMPUTER_IT`, `NONE`)가 정의되어 있으며, 도서 등록 서버(`backend-book`)가 도서 데이터를 저장하기 전에 이 16개 표준 장르 중 가장 적합한 1개로 정확하게 매핑하는 기능이 필요하다.

## 결정 사항
1. **경량 REST API 엔드포인트 신설 및 확장**:
   - `POST /api/v1/classify-genre`
   - 요청: `BookClassificationRequest` (`isbn: str = ""` (선택), `title: str`, `author: str = ""`, `raw_category: str = ""`)
   - 응답: `BookClassificationResponse` (`genre: StandardGenre`, `confidence: float = 1.0`)
   - 호출 주체: `backend-book` (도서 저장 서버가 OCR 텍스트/ISBN 추출 후 장르 분류 호출)
   - 2026-08-29 업데이트: `isbn` 필드를 선택으로 추가하여, 도서 고유 식별자가 제공될 경우 LLM 프롬프트에 우선 분석 단서로 제공하고 미제공 시 기존 필드로 fallback 처리.

2. **분류 엔진 및 모델**:
   - AWS Bedrock Claude 3 Haiku (`anthropic.claude-3-haiku-20240307-v1:0`)를 활용하여 제로샷(Zero-shot) 정밀 프롬프트 분류 수행.
   - 비용 및 속도 최적화를 위해 경량 단일 턴 호출 방식으로 동작.
   - `core/config.py`의 `genre_classifier_model_id` 환경변수로 모델 교체 용이성 확보.

3. **안전장치 (Robust Fallback)**:
   - LLM 출력이 비정형 텍스트이거나 마크다운 코드블록을 포함하더라도 안전하게 JSON 및 Enum을 추출하는 도메인 파서(`parse_classification_response`) 및 완화 키워드 매처(`match_standard_genre`) 구현.
   - LLM 호출 실패 또는 미식별 장르인 경우 500 에러를 유발하지 않고 `StandardGenre.NONE`("미식별")과 낮은 confidence(0.0)로 graceful fallback.
   - 로컬 테스트 및 CI 환경(`llm_provider=="mock"`)을 위해 규칙 기반 결정론적 Mock 분류기 지원.

## 결과 및 영향
- 도서 등록 파이프라인에서 단일 API 호출로 표준 장르 정제가 가능해짐.
- `backend-book` DB `genre_type` Enum과의 100% 일치로 데이터 불일치 해소.
