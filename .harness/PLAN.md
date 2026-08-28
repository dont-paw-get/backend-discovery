# PLAN — backend-discovery

## [진행 예정] CLIAR-152 후속 및 프론트엔드 실연동 검증

올인원 독서 비서 백엔드 배선 완료 후, 프론트엔드 단일 챗 UI 연동 및 K8s 배포 환경 E2E 검증.

---

### 단계별 Task 체크리스트

#### Task 1: 프론트엔드(`my-reading-room`) 단일 챗 UI 연동 및 헤더 전달
- [ ] 프론트엔드 `POST /api/v1/chat` 호출 시 `Authorization: Bearer <token>` 헤더 전달 확인
- [ ] 프론트엔드 모드 선택 UI 제거 및 단일 자연어 입력창에서 내 서재 질문 / 추천 질문 / 복합 질문 실시간 스트리밍 동작 확인

#### Task 2: K8s dev 환경 배포 및 서재 API 통신 검증
- [ ] K8s 클러스터 내부 및 ELB 도메인(`http://k8s-dpybbook-backendb-d17a725d36-1113312703.ap-northeast-2.elb.amazonaws.com`) 통신 실측
- [ ] 서재 미등록 사용자 또는 인증 실패 시 graceful fallback UI 연출 확인

