# BACKLOG — backend-discovery

지금 하지 않지만 나중에 할 것.

## 신규 티켓 후보

- [ ] **CSV 배치 도서 데이터 적재** — Basic API로부터 전달받은 도서 데이터(하루 최대 5,000건,
  총 약 25만 건)를 CSV 배치로 읽기 모델에 적재한다. 25만 건 규모의 원본 CSV 파일은 이미
  전달받은 상태라 다음 티켓에서 바로 착수 가능하다. 범위: (1) 25만 건 규모 배치 처리
  (스트리밍/청크 단위 임베딩+upsert, 메모리 사용량 고려), (2) 동시성 제어(임베딩 API
  rate limit 대응, 병렬 처리 정도 결정), (3) 실패 시 재시도 전략(행 단위 실패 격리,
  재시도 가능/불가능 에러 구분), (4) 멱등성 확보(`BookRepository.upsert`를 CSV
  배치에서도 재사용해 재실행 시 중복 없음 보장). `/internal/sync-book`(단건 동기 HTTP)은
  이 배치의 대체 수단이 아니라 실시간 갱신·테스트 전용이므로 이 티켓과 무관하게 유지한다
  (`.harness/DECISIONS.md` 참고).

## 기술 부채 / 후속 과제
- [ ] `search_vector`(tsvector)가 `simple` config를 사용해 한글 조사가 붙은 단어(예: "위로가")가 그 자체로 하나의 lexeme이 되어 정확한 형태로만 매칭된다. 한국어 형태소 분석기(예: PostgreSQL 확장 `pg_bigm`, 또는 외부 mecab 기반 토크나이저)를 검토해 검색 품질을 개선해야 한다. 지금은 GIN 인덱스·하이브리드 검색 인프라 자체의 동작 검증이 목적이라 `simple`로 충분하지만, 실사용 단계에서는 재검토 필요.
- [ ] Bedrock 실연동 — Mock을 실제 `BedrockRuntimeClient`로 교체. 임베딩 차원 1536 재검증 필요
- [ ] 임베딩 모델 변경 시 `vector(1536)` 컬럼 마이그레이션 전략 수립 (재임베딩 배치 포함)
- [ ] `/internal/*` 인증을 공유 시크릿 → mTLS 또는 VPC 내부 제한으로 승격
- [ ] Basic API → Discovery 동기화 실패 시 재시도/DLQ 설계 (현재는 HTTP 단건 동기 호출)
- [ ] HNSW 파라미터(`m`, `ef_construction`, `ef_search`) 실데이터 기반 튜닝
- [ ] 대화 세션 요약 압축 — 토큰 한도 초과 시 오래된 턴 요약 전략
- [ ] CI 워크플로우에 ruff/mypy/pytest(unit+integration) 추가
- [ ] 관측성: 구조적 로깅, 요청 추적 ID, RAG 검색 품질 지표 수집
