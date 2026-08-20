# BACKLOG — backend-discovery

지금 하지 않지만 나중에 할 것.

## 기술 부채 / 후속 과제
- [ ] Bedrock 실연동 — Mock을 실제 `BedrockRuntimeClient`로 교체. 임베딩 차원 1536 재검증 필요
- [ ] 임베딩 모델 변경 시 `vector(1536)` 컬럼 마이그레이션 전략 수립 (재임베딩 배치 포함)
- [ ] `/internal/*` 인증을 공유 시크릿 → mTLS 또는 VPC 내부 제한으로 승격
- [ ] Basic API → Discovery 동기화 실패 시 재시도/DLQ 설계 (현재는 HTTP 단건 동기 호출)
- [ ] HNSW 파라미터(`m`, `ef_construction`, `ef_search`) 실데이터 기반 튜닝
- [ ] 대화 세션 요약 압축 — 토큰 한도 초과 시 오래된 턴 요약 전략
- [ ] CI 워크플로우에 ruff/mypy/pytest(unit+integration) 추가
- [ ] 관측성: 구조적 로깅, 요청 추적 ID, RAG 검색 품질 지표 수집
