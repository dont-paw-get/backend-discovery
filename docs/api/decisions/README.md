# docs/api/decisions — API 계약 결정 기록 (ADR)

API wire 계약에 대한 결정과 근거를 append 방식으로 쌓는 디렉토리다.
아키텍처/워크플로우 결정은 `.harness/DECISIONS.md`가 소유하지만,
**API 계약** 관련 결정(엔드포인트 설계, 호환성 깨는 변경, 인증 방식 선택 등)은
여기에 개별 ADR 파일로 기록한다.

## 파일 규칙

- 파일명: `NNNN-짧은-제목.md` (번호는 4자리, 0001부터 순차 증가)
- 아직 ADR이 작성되지 않았다. 첫 ADR(`0001-internal-sync-contract.md` — Basic API가
  push하는 단건 동기 HTTP 방식 채택)은 `.harness/PLAN.md`의 Task 9에서 작성한다.
