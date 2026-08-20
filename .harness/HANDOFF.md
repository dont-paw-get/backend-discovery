# HANDOFF — backend-discovery

세션마다 무엇을 했는지 append-only로 기록한다.

## 2026-08-19 — 하네스 스캐폴딩 및 계획 수립
- 브랜치: `CLIAR-21-FastAPI-Scaffolding` (develop 분기)
- `AGENTS.md` 정독 후 `.harness/` 6종 문서와 `docs/api/` 뼈대를 생성했다.
- 정책 충돌 2건을 사용자와 확정: 의존성 파일은 `pyproject.toml`(uv) 채택, `docs/api/` 계약 산출물 선행 작성.
- `AGENTS.md`의 origin 주소가 `backend-book.git`으로 잘못 적혀 있어 `backend-discovery.git`으로 정정했다.
- 코드는 작성하지 않았다. `PLAN.md`에 3스텝 체크리스트만 확정한 상태로 종료한다.

### 다음 세션이 할 일
1. `PLAN.md` Step 1의 첫 항목(`pyproject.toml` 작성)부터 착수.
2. 커밋·push·PR은 사용자가 별도 요청할 때까지 수행하지 않는다.
3. 체크리스트 항목을 끝낼 때마다 `PLAN.md`에서 제거하고 `STATE.md`에 단계 한 줄로 반영한다.


## 2026-08-20 — CLIAR-21 인프라 세팅(Task 1~4) 완료, 브랜치명 정정
- CLIAR-21 인프라 세팅(Task 1~4: pyproject.toml/uv, docker-compose/Dockerfile, FastAPI 앱+/health, Alembic+테스트 픽스처)을 모두 완료했다.
- 로컬 브랜치명을 `CLIAR-21-FastAPI-Scaffolding`에서 `CLIAR-21-Infra-Setup`으로 rename했다(`git branch -m`). Jira 티켓 제목도 "인프라 세팅"으로 이미 수정 완료된 상태다.
  - 주의: 로컬 브랜치는 여전히 `origin/CLIAR-21-FastAPI-Scaffolding`을 추적(tracking) 중이다. push하지 않았으므로 원격 브랜치명은 아직 이전 이름 그대로다. 원격도 맞추려면 별도로 push(및 필요 시 원격 브랜치 rename/재생성)가 필요하며, 이번 세션에서는 수행하지 않았다.
- 다음 스텝(기존 계획의 Step 2 핵심 코드 구현 / Step 3 API 라우터 구현에 해당하는 작업)은 별도 티켓으로 진행할 예정이나, 세부 범위와 분할 방식(하나의 티켓으로 묶을지, Step 2/Step 3을 나눌지 등)은 아직 미확정이다. 다음 세션에서 재논의한다.
- `PLAN.md`의 Step 2/3 항목은 사용자 지시에 따라 이번 세션에서 손대지 않고 그대로 두었다. 분리 여부·새 파일 구조(`PLAN-CLIAR-22.md` 등)는 다음 티켓 범위가 확정된 뒤 다시 논의한다.
- 이 세션은 CLIAR-21 마감으로 종료한다. 코드/문서 추가 작업 없음.

### 다음 세션이 할 일
1. 다음 티켓 번호와 범위(Step 2/3의 분할 방식)를 사용자로부터 받아 `PLAN.md` 처리 방식을 논의한다.
2. 원격 브랜치명을 로컬과 맞출지(push 방식) 사용자와 확인한다.
3. 커밋·push·PR은 사용자가 명시적으로 요청할 때까지 수행하지 않는다.
