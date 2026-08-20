# docs/api — backend-discovery API 계약

이 디렉토리가 backend-discovery의 **API wire 계약의 단일 소유 산출물**이다.
`.harness/*`는 이 내용을 복제하지 않고 참조만 한다 (AGENTS.md "하네스: 변경 산출물 동기화" 정책).

## 소유권

| 파일 | 담는 내용 |
| --- | --- |
| `openapi.yaml` | 엔드포인트, 요청/응답 스키마, 에러 응답, 인증 방식(security scheme) |
| `decisions/` | API 계약과 관련된 결정과 근거 (ADR) |
| 이 `README.md` | 문서 탐색 방법, 검증 방법 |

API 엔드포인트나 요청/응답 스키마를 변경할 때는 `openapi.yaml`을 먼저 수정하고,
호환성이 깨지거나 정책 근거가 필요하면 `decisions/`에 ADR을 추가한 뒤 Router·Pydantic
Schema·계약 테스트를 함께 갱신한다.

## 현재 상태

`openapi.yaml`은 아직 스켈레톤이다. 3개 엔드포인트(`POST /chat`, `GET /curations/time-based`,
`POST /internal/sync-book`)의 경로와 보안 스키마(`X-Internal-Token`)만 자리를 잡아두었고,
상세 요청/응답 스키마 확정은 `.harness/PLAN.md`의 Task 9에서 수행한다.

## 스펙 검증 방법

```bash
uvx --from openapi-spec-validator openapi-spec-validator docs/api/openapi.yaml
```

## Swagger UI / Redoc으로 열람하기

로컬에 Node.js가 있다면 다음 중 하나로 즉시 렌더링해서 볼 수 있다.

```bash
# Swagger UI
npx -y swagger-ui-watcher docs/api/openapi.yaml

# 또는 Redoc
npx -y @redocly/cli preview-docs docs/api/openapi.yaml
```

앱이 기동된 상태라면 FastAPI가 생성하는 `/docs`(Swagger UI), `/redoc`도 참고할 수 있다.
단, 코드가 생성한 스키마와 이 `openapi.yaml`이 어긋나지 않는지는 계약 테스트
(`.harness/PLAN.md` Task 13)로 검증한다.
