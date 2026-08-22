# S3 Vectors 전환 검토 — backend-discovery

- 조사일: 2026-08-21
- 관련 티켓: 없음 (CLIAR-51과 무관한 별도 조사 요청)
- 상태: 조사 완료, 결정 대기 (팀 논의 후 사용자가 결정)

## 조사 대상 조건 (우리 서비스 실측 기준)

- 도서 규모: 약 25만 건
- 쿼리 패턴: 챗봇 서비스 — 사용자가 대화할 때마다 벡터 검색 발생. 사용자 대기 중
  실시간 응답이 필요한 **interactive, 높은 QPS 지향** 워크로드
- 현재 구조: PostgreSQL + pgvector(HNSW) + tsvector(GIN)를 같은 DB에서 하이브리드로
  결합 (`.harness/DECISIONS.md` 2026-08-20 결정, 현재 기본값은 벡터 단독, 하이브리드는
  옵션)

## 1. 비용 이점이 실제로 있는가

**결론: 이 규모/패턴에서는 이점이 없거나 오히려 불리할 가능성이 높다.**

- S3 Vectors는 스토리지 비용($0.06/GB)이 저렴하고 쿼리당 과금(pay-per-query) 모델이라,
  **쿼리 빈도가 낮고 데이터가 크거나(수억~수십억 벡터) 계속 커지는 워크로드**에서
  기존 벡터 DB(전용 인스턴스 상시 기동) 대비 최대 90%까지 비용을 줄인다고 AWS는
  설명한다. [출처: AWS ML 블로그](https://aws.amazon.com/blogs/machine-learning/aws-vector-solutions-build-agentic-ai-where-your-data-lives/)
- 반대로 AWS의 공식 벡터 DB 선택 가이드는 S3 Vectors를 다음 상황에 권장한다:
  "billions of vectors", "infrequent access/retrieval patterns", "long-term
  retention", "cost optimization over ultra-low latency". [출처: AWS Prescriptive
  Guidance](https://docs.aws.amazon.com/prescriptive-guidance/latest/choosing-an-aws-vector-database-for-rag-use-cases/vector-db-options.html)
- 우리 조건은 정반대에 가깝다: 25만 건은 S3 Vectors가 최적화된 "billion-scale"과
  자릿수 차이가 크고(약 1/1000~1/10000 규모), 챗봇 서비스는 "infrequent query"가
  아니라 사용자가 쓸 때마다 실시간 쿼리가 발생하는 **interactive 워크로드**다.
- 비용 모델 관점에서도 pay-per-query는 "쿼리가 드문드문 발생"할 때 유리한 구조다.
  트래픽이 꾸준히 발생하는 챗봇이라면 이미 떠 있는 PostgreSQL 인스턴스(다른 읽기
  모델 데이터도 같이 서비스 중)에서 HNSW 인덱스로 추가 쿼리를 처리하는 것이 인스턴스
  비용을 어차피 지불하고 있는 상태에서는 오히려 한계비용이 낮다. S3 Vectors로
  옮기면 쿼리 건수만큼 추가 과금이 새로 발생한다.
- 결론적으로 "데이터를 인위적으로 부풀리지 않는" 우리의 실제 조건(25만 건, 높은
  쿼리 빈도)에서는 S3 Vectors가 최적화 대상으로 삼는 조건과 맞지 않아 비용 이점을
  기대하기 어렵다.

## 2. 지연시간이 챗봇 응답 속도에 미치는 영향

**결론: 챗봇처럼 사용자가 대기하는 대화형 응답에는 부담이 되는 지연시간이다.**

- AWS 공식 자료 기준 S3 Vectors 쿼리 지연시간:
  - GA 시점 기준: "infrequent queries continue to return results in under one
    second, with more frequent queries now resulting in latencies around 100ms
    or less" [출처: AWS News Blog](https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance/)
  - FAQ 기준: "sub-second query latency", "ideal for infrequent query
    workloads" [출처: AWS S3 FAQ](https://aws.amazon.com/s3/faqs/)
  - 다른 AWS 블로그(Aurora+S3 Vectors 통합 사례)의 실측 비교: "S3 Vectors delivers
    sub-second query performance for cold queries and less than 100ms for warm
    queries", 반면 "Aurora pgvector delivers single-digit millisecond response
    times" [출처: AWS DB 블로그](https://aws.amazon.com/blogs/database/query-billion-scale-vectors-with-sql-integrating-amazon-s3-vectors-and-aurora-postgresql/)
- 즉 최선의 경우(캐시된 warm 쿼리)에도 ~100ms, 최악의 경우(cold) 1~3초까지 걸릴 수
  있다. 반면 우리가 현재 쓰는 pgvector+HNSW는 자체 인스턴스에서 single-digit
  millisecond(수 ms) 응답이 기본이다.
- 챗봇 응답 파이프라인(`.harness/PLAN.md` Task 12 설계 기준)은 벡터 검색 →
  LLM 프롬프트 조립 → LLM 호출의 순차 흐름이다. 벡터 검색 단계에 사용자가 이미
  기다리는 LLM 호출 지연시간(보통 수백 ms~수 초) 위에 추가로 최대 1~3초가 더해지면
  전체 응답 시간이 체감상 느려질 위험이 크다.
- AWS 자체도 "conversational AI and multi-agent workflows"에는 ~100ms 이하의
  최적 케이스를 언급하지만, 이는 "warm(캐시된)" 쿼리 기준이며 cold 쿼리에서는
  여전히 초 단위로 벌어질 수 있다는 점을 같은 자료에서 명시한다.

## 3. 현재 tsvector+GIN 하이브리드 검색을 S3 Vectors에서 유지할 수 있는가

**결론: 유지할 수 없다. 메타데이터 필터링만 가능하고, 우리가 쓰는 PostgreSQL
전문검색(Full-Text Search) 방식의 하이브리드는 S3 Vectors 자체에 없다.**

- S3 Vectors의 메타데이터 필터링은 `$eq`, `$ne`, `$gt`, `$in` 같은 **정확 매칭/비교
  연산자** 기반이다. `category`, `synced_at` 같은 구조화된 필드를 필터링하는 데는
  쓸 수 있지만, `tsvector`가 하는 것과 같은 텍스트 랭킹/키워드 매칭(BM25류)은
  지원하지 않는다. [출처: AWS S3 Vectors 메타데이터 필터링 문서](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-metadata-filtering.html)
- 이는 AWS 자체 자료로도 명확히 확인된다: S3 Vectors는 "Hybrid search: ❌ No BM25 +
  vector"이며, 반면 비교 대상인 OpenSearch는 "✅ Native hybrid"로 명시된다.
  [출처: AWS Prescriptive Guidance — Technology Tradeoffs](https://docs.aws.amazon.com/prescriptive-guidance/latest/semantic-layer-agentic-ai-ontology-reasoning-virtual-knowledge-graph/technology-tradeoffs-alternatives.html)
- 우리가 CLIAR-40에서 만든 `search_vector`(tsvector, `to_tsvector('simple', ...)`)
  기반 하이브리드는 벡터 유사도와 키워드 전문검색을 **같은 PostgreSQL 쿼리 안에서**
  결합한다(`book_repository.py`의 `search_by_embedding(use_hybrid_search=True)`).
  이 방식을 S3 Vectors로 그대로 가져갈 수 없다.
- S3 Vectors로 전환하면서 하이브리드 검색을 유지하려면 실질적으로 다음 중 하나가
  필요하다:
  1. 벡터는 S3 Vectors, 메타데이터/키워드 검색은 별도로 PostgreSQL(또는
     OpenSearch)에 두고 애플리케이션 계층에서 두 결과를 병합 — 즉 **저장소를
     분리**해야 하고, 지금처럼 "하나의 쿼리"가 아니라 두 시스템을 호출해 합치는
     추가 로직과 지연시간이 필요해진다.
  2. 키워드 검색까지 S3 Vectors의 메타데이터 필터(정확 매칭)로 흉내내려 하면
     `tsvector`가 제공하는 자연어 랭킹 품질을 잃는다.
  - AWS도 "S3 Vectors as cold storage + OpenSearch Service for hot queries"
    같은 티어링 아키텍처를 권장 패턴으로 제시하는데, 이는 "메타데이터 DB와
    분리"가 S3 Vectors 채택의 기본 전제라는 뜻이다.

## 종합 결론

**전환 비권장.**

세 가지 조사축 모두 우리 서비스 조건과 S3 Vectors가 최적화된 조건이 반대 방향을
가리킨다:

| 축 | 우리 서비스 조건 | S3 Vectors 최적 조건 | 판정 |
| --- | --- | --- | --- |
| 규모 | 25만 건 | 수억~수십억(빌리언 스케일) | 불일치 |
| 쿼리 빈도 | 높음(사용자가 쓸 때마다) | 낮음(infrequent) | 불일치 |
| 지연시간 허용치 | 챗봇 대화형(빠를수록 좋음) | ~100ms~수 초 허용 | 불일치 |
| 하이브리드 검색 | 필요(현재 설계에 이미 존재) | 미지원(메타데이터 필터만) | 불일치 |

pgvector(HNSW) + tsvector(GIN) 조합을 그대로 유지하는 것이 현재 규모와 쿼리
패턴에서는 비용·지연시간·기능(하이브리드) 세 축 모두에서 더 낫다. S3 Vectors는
도서 데이터가 수천만~수억 건 규모로 커지고 조회가 뜸해지는 별도 시나리오(예:
"오래된 저활동 도서의 콜드 아카이브 검색")가 생기면 재검토할 만하지만, 지금
서비스의 핵심 RAG 챗봇 경로에는 적용하지 않는 것을 권장한다.

## 참고 자료

- [AWS S3 FAQs — S3 Vectors 비용/성능 Q&A](https://aws.amazon.com/s3/faqs/)
- [AWS ML 블로그 — AWS vector solutions](https://aws.amazon.com/blogs/machine-learning/aws-vector-solutions-build-agentic-ai-where-your-data-lives/)
- [AWS News 블로그 — S3 Vectors GA 발표](https://aws.amazon.com/blogs/aws/amazon-s3-vectors-now-generally-available-with-increased-scale-and-performance/)
- [AWS DB 블로그 — S3 Vectors + Aurora pgvector 통합](https://aws.amazon.com/blogs/database/query-billion-scale-vectors-with-sql-integrating-amazon-s3-vectors-and-aurora-postgresql/)
- [AWS Prescriptive Guidance — Vector database options](https://docs.aws.amazon.com/prescriptive-guidance/latest/choosing-an-aws-vector-database-for-rag-use-cases/vector-db-options.html)
- [AWS Prescriptive Guidance — Technology Tradeoffs & Alternatives](https://docs.aws.amazon.com/prescriptive-guidance/latest/semantic-layer-agentic-ai-ontology-reasoning-virtual-knowledge-graph/technology-tradeoffs-alternatives.html)
- [AWS S3 Vectors — Metadata filtering](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-metadata-filtering.html)

이 문서는 `.harness/research/`에 조사 결과로만 보관하며, 결정이 확정되면
`.harness/DECISIONS.md`에 결정 사항과 근거를 옮겨 기록한다 (현재는 조사 단계이므로
DECISIONS.md에는 기록하지 않았다).
