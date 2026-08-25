# BACKLOG — backend-discovery

지금 하지 않지만 나중에 할 것.

## 기술 부채 / 후속 과제
- [ ] Bedrock 모델 가용성 — Haiku 4.5/Sonnet 4 이상은 `kosa-edu-region-pol`로 전
  리전 차단 확인. Claude 3 Haiku, Claude 3.5 Sonnet은 사용 가능 확인됨. 현재
  기본값은 Haiku, 필요 시 Sonnet 3.5로 특정 기능 업그레이드 검토.
- [ ] `search_vector`(tsvector)가 `simple` config를 사용해 한글 조사가 붙은 단어(예: "위로가")가 그 자체로 하나의 lexeme이 되어 정확한 형태로만 매칭된다. 한국어 형태소 분석기(예: PostgreSQL 확장 `pg_bigm`, 또는 외부 mecab 기반 토크나이저)를 검토해 검색 품질을 개선해야 한다. 지금은 GIN 인덱스·하이브리드 검색 인프라 자체의 동작 검증이 목적이라 `simple`로 충분하지만, 실사용 단계에서는 재검토 필요.
- [ ] Bedrock 실연동 — Mock을 실제 `BedrockRuntimeClient`로 교체. 임베딩 차원 1536 재검증 필요
- [ ] 임베딩 모델 변경 시 `vector(1536)` 컬럼 마이그레이션 전략 수립 (재임베딩 배치 포함)
- [ ] `/internal/*` 인증을 공유 시크릿 → mTLS 또는 VPC 내부 제한으로 승격
- [ ] Basic API → Discovery 동기화 실패 시 재시도/DLQ 설계 (현재는 HTTP 단건 동기 호출)
- [ ] HNSW 파라미터(`m`, `ef_construction`, `ef_search`) 실데이터 기반 튜닝
- [ ] 대화 세션 요약 압축 — 토큰 한도 초과 시 오래된 턴 요약 전략
- [ ] CI 워크플로우에 ruff/mypy/pytest(unit+integration) 추가
- [ ] 관측성: 구조적 로깅, 요청 추적 ID, RAG 검색 품질 지표 수집
- [ ] Agents-as-Tools 리팩터링, 사서 연동, ArgoCD 배포 확정 후 `docs/api/openapi.yaml`을 최신 상태로 갱신하고 프론트 담당자에게 공유. 프론트가 axios 클라이언트를 서버별로 작성할 수 있게 엔드포인트/스키마/인증 헤더/CORS 설정을 명확히 문서화.