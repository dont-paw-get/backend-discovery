# PLAN — backend-discovery

## [완료] 내 서재 도서 구조화 데이터(library_books) 응답 및 "책 열기" 연동 계약 구축 [CLIAR-196]

모든 Task가 완료되어 `.harness/STATE.md`에 반영되었습니다.

---

### [참고] 후속 대기 과제 (2차 고도화)
1. **복합 추천 시 서재 도서 카드 노출 억제**: 사용자가 '서재 도서 기반 새로운 책 추천'을 요청하여 `search_my_library` ➔ `recommend_books`가 연쇄 실행될 때, 서재 도서는 추천의 재료이므로 `library_books`를 노출하지 않도록 억제하는 조건 분기 고도화 (1차 실측 및 사용자 체감 확인 후 착수).
2. 프론트엔드(`my-reading-room`) 배포 후 `library_books` 데이터를 읽어 기존 서재 상세 모달/라우트(`/library/books/{book_id}`)로 연결하는 "책 열기" 버튼 E2E 검증.




