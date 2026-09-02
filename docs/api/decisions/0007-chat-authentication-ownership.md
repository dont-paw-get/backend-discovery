# ADR 0007: 대화(Chat) 엔드포인트 인증 소유권 및 헤더 존재 검증(Presence Check) 채택

- **상태**: Accepted
- **날짜**: 2026-09-02
- **관련 티켓**: CLIAR-215 (Task 2)
- **참여**: 아키텍처 및 API 보안 도메인

---

## 1. 배경 및 문제점

1. **무인증 요청 허용 및 보안 공백**:
   - 기존 `POST /api/v1/chat` 엔드포인트는 `Authorization` 헤더를 `Header(default=None)`으로 받아 서재 도서 조회 도구(`SearchMyLibraryTool`)로만 패스스루하고 있었음.
   - Discovery 레벨에서 헤더 검증이 전혀 없어, `Authorization` 헤더 없이 호출하거나 위조된 토큰을 전달해도 `200 OK`로 응답이 생성되고 서재만 빈 목록으로 처리되는 보안/정책적 공백이 QA 46건 실측에서 확인됨 (QA 18번, 19번).
2. **인프라 현실과 옵션 비교**:
   - **Option A (Discovery 자체 서명/만료 검증)**: Discovery에 JWT 시크릿/공개키/JWKS 연동이 전혀 없어 새로 구축해야 하며, 이는 인증 서비스와의 별도 계약 수립이 필요한 큰 범위 확장에 해당함.
   - **Option B (순수 게이트웨이 신뢰)**: `k8s/base/ingress.yaml` 확인 결과 ALB에 인증 어노테이션이 전혀 없어 "게이트웨이가 이미 검증했다"는 전제가 성립하지 않으며, 이 옵션을 택하면 `/api/v1/chat`이 완전 무인증으로 방치됨.

---

## 2. 결정 사항

### 2.1 헤더 존재 검증 (Presence Check) 채택
- Discovery 서비스의 `POST /api/v1/chat` 엔드포인트는 **헤더 존재 검증(Presence Check)**을 수행한다.
- `Authorization` 헤더가 누락되었거나 `.strip()` 후 빈 문자열인 경우, FastAPI 의존성(`require_authorization_header`) 단계에서 즉시 `401 Unauthorized` (`detail="Authorization header is required"`)를 반환한다.
- 이 결정은 본 프로젝트의 `/internal/*` 라우터가 공유 시크릿 헤더 존재/일치를 검증하던 기존 보안 아키텍처 패턴(`DECISIONS.md` 2026-08-19)과 일관된다.

### 2.2 서명 및 만료 실질 검증의 위임과 `on_auth_failed` 콜백
- JWT 토큰의 실제 서명 유효성 및 만료 여부는 `backend-book`(서재 API) 호출 시 해당 서비스의 응답(401)을 통해 전달받아 처리한다.
- `SearchMyLibraryTool`이 `backend-book`으로부터 401을 수신하면 `LibraryAuthError`를 발생시키고, `@tool` 래퍼는 `on_auth_failed` 콜백을 호출하여 서비스 레이어에 신호를 전달한다.
- **동기 응답(`chat`)**: `on_auth_failed` 신호 감지 시 `HTTPException(401, detail="Library API authentication failed")`을 발생시켜 클라이언트에 401을 전달한다.
- **스트리밍 응답(`stream_chat`) 구조적 한계**: `StreamingResponse`는 도구 실행 전인 TTFB 시점에 이미 `200 OK` 헤더를 확정하여 브라우저에 전송하므로, 중간에 HTTP 상태 코드를 401로 변경할 수 없다. 따라서 스트리밍 경로에서는 경고 로그를 남기고 도구가 반환한 안내 문구("인증 정보가 유효하지 않아 서재를 조회할 수 없습니다")가 자연스러운 텍스트로 사용자에게 전달되도록 한다.
- 향후 완전한 서명 검증이 게이트웨이(ALB/BFF) 또는 Discovery 자체에 필요해지는 경우 백로그로 이관하여 별도 인프라로 고도화한다.

### 2.3 `SearchMyLibraryTool` 방어 로직 유지
- `SearchMyLibraryTool` 내부의 `auth_token` 미존재 시 빈 리스트 반환 로직은 라우터 계층에서 이미 걸러지지만, 하위 도구 레벨의 심층 방어(Defense in Depth) 차원에서 보존한다.

---

## 3. 파급 효과
- **QA 18번(헤더 누락) 즉시 방어**: `Authorization` 헤더 미전달 시 401 에러로 명확히 거부.
- **오동작 방지**: `SearchMyLibraryTool`이 인증 토큰 없이 호출되어 사용자의 의도와 달리 조용히 빈 서재 결과를 반환하던 오동작을 진입점에서 원천 차단.
- **불필요한 인프라 비대화 방지**: 별도 JWT 검증 라이브러리/키 관리 인프라 추가 없이 경량화된 보안 게이트 확보.
