# PLAN — backend-discovery

## [완료] 사서 로컬 페르소나 fallback 의도 게이트 고도화 및 하드코딩 응답 제거 [CLIAR-208]

모든 Task(Task 1~5)가 완료되어 `.harness/STATE.md`에 반영되었습니다.

---

### 💡 후속 대기 과제
1. **서재 응답 실호출 CTA 샘플링 확인**: K8s dev 배포 후 Bedrock 실호출 시 서재 조회 응답의 CTA가 매번 고정된 복붙 문장이 아니라 책 내용과 장르에 맞게 유연하게 생성되는지 확인.
2. **복합 추천 시 `library_books` 노출 억제 분기 고도화**: 사용자가 '서재 도서 기반 새로운 책 추천'을 요청하여 `search_my_library` ➔ `recommend_books`가 연쇄 실행될 때 `library_books`를 노출하지 않도록 억제하는 조건 분기.
3. **프론트엔드 배포 후 '책 열기' E2E 연동 검증**: 프론트엔드가 `response.library_books`를 읽어 [책 열기] 버튼으로 상세 뷰를 여는지 검증.








