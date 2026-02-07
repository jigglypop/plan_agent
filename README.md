# Plan Agent

AI 기반 기획위원회 PM/통계 시스템

## 기능

- 행사 통계 분석 (20개+ 지표)
- PM 업무 자동화 (일정/태스크/리마인더)
- AI 어시스턴트 (GPT 연동)
- 벡터 DB 시맨틱 검색 (ChromaDB)
- 노션 연동
- MCP 서버 (Cursor 연동)

## 기술 스택

- **Backend**: Python, FastAPI, uvicorn
- **Frontend**: React, TypeScript, Vite, Recharts
- **AI**: OpenAI GPT-4o
- **Vector DB**: ChromaDB
- **Integration**: Notion API, MCP

## 설치

```bash
# Backend
uv sync

# Frontend
cd frontend && npm install
```

## 환경 변수

`.env` 파일 생성:

```env
OPENAI_API_KEY=sk-...
NOTION_TOKEN=ntn_...
NOTION_DATABASE_ID=
MENSA_USERNAME=
MENSA_PASSWORD=
```

## 실행

```bash
# Backend API (http://localhost:8000)
uv run python run_server.py

# Frontend (http://localhost:5173)
cd frontend && npm run dev

# MCP Server (Cursor용)
uv run python run_mcp.py
```

## 프로젝트 구조

```
plan_agent/
├── src/
│   ├── agent/         # AI 에이전트
│   ├── api/           # FastAPI 서버
│   ├── crawler/       # 크롤러 (멘사코리아)
│   ├── data/          # 데이터 스키마
│   ├── mcp_server/    # MCP 서버
│   ├── notion/        # 노션 연동
│   ├── pm/            # PM 기능
│   ├── stats/         # 통계 분석
│   └── vectordb/      # 벡터 DB
├── frontend/          # React 프론트엔드
├── docs/              # 문서
└── .cursor/           # MCP 설정
```

## API 엔드포인트

| 엔드포인트 | 설명 |
|------------|------|
| GET /stats | 전체 통계 |
| GET /events | 행사 목록 |
| GET /tasks | 태스크 목록 |
| POST /chat | AI 채팅 |
| GET /reminders | 리마인더 |

## MCP 도구

| 도구 | 설명 |
|------|------|
| search_events | 행사 시맨틱 검색 |
| search_tasks | 태스크 검색 |
| get_stats_summary | 통계 요약 |
| get_upcoming_events | 다가오는 행사 |
| get_overdue_tasks | 기한 초과 태스크 |

## 리팩토링 플랜 (운영 안정화 + 인덱싱/배치 보강)

### 범위/원칙

- **목표**: 운영 안정성(재시작/장애), 관측 가능성(로깅/헬스), 인덱싱 비용/시간 절감(증분), 데이터 정합성(검증).
- **원칙**: DRY/KISS/SRP, 불필요한 파일/함수 이름 변경 금지, 임시/더미 파일 금지, 이모지 사용 금지.

### 현재 구조의 핵심 문제점

- **로깅 부재**: 대부분 `print()` 기반이라 레벨/타임스탬프/모듈 컨텍스트/추적이 어렵습니다. (예: `src/vectordb/store.py`, `src/data/parser.py`, `src/crawler/mensa.py`, `src/discord/bot.py`, `src/notion/client.py`)
- **VectorDB 인덱싱 정합성/증분 처리 없음**: 컨테이너 시작 시(`entrypoint.sh`) `python -m src.vectordb.store`를 무조건 실행하지만,
  - `crawled.json`과 Chroma 인덱스가 **일치하는지 검증**하지 않습니다.
  - **변경분만** 인덱싱하는 로직이 없어 비용/시간이 증가할 수 있습니다.
- **인덱싱 엔트리포인트 혼합**: `src/vectordb/store.py`가 모듈 실행 시 인덱싱뿐 아니라 “검색 테스트”까지 수행합니다.
- **세션 메모리 무한 성장**: `src/agent/core.py`의 `_sessions`가 TTL/LRU 없이 계속 늘어날 수 있습니다.
- **API 계약 불일치**: 프론트 `resetChat()`은 JSON body로 `session_id`를 보내는데, 서버는 쿼리 파라미터로만 받는 형태입니다. (`frontend/src/api.ts`, `src/api/server.py`)
- **데이터 손실 위험**: Chroma 초기화 실패 시 `persist_dir`를 `rmtree`로 삭제하는 경로가 있습니다. (`src/vectordb/store.py`)
- **보안 기본값**: CORS가 `allow_origins=["*"]`로 전면 허용입니다. (`src/api/server.py`)
- **문서 싱크 불일치**: 실행/구조 설명이 실제 파일과 일부 다를 수 있습니다(예: `run_server.py`, `run_mcp.py`).

### 단계별 실행 계획 (변경 최소화, 효과 최대화)

#### Phase 0 (P0) - 즉시 안정화

- **인덱싱을 “인덱싱 전용”으로 분리**
  - `python -m src.vectordb.store` 실행 경로에서 “검색 테스트”를 제거하거나 옵션으로 분리.
  - `entrypoint.sh`는 “인덱싱 전용” 경로만 호출.
- **VectorDB 폴더 삭제 방지**
  - 초기화 실패 시 무조건 `rmtree` 대신, 안전하게 중단하거나 env 플래그로만 reset 허용.
- **reset API 계약 맞추기**
  - 서버가 JSON body를 받도록 하거나, 프론트가 쿼리로 보내도록 통일.

#### Phase 1 (P1) - 로깅/헬스체크(관측 가능성)

- **표준 로깅 도입**
  - 모듈별 `logger = logging.getLogger(__name__)`로 통일, `print()` 제거.
  - 최소 로그: 시작/종료, 인덱싱/파싱 진행률, API 요청 실패/예외, 도구 호출 요약.
- **/api/health 확장**
  - 게시글 로딩 여부/개수, VectorDB count, 인덱싱 정합성(Phase 2 결과)을 포함.

#### Phase 2 (P1) - 인덱싱 정합성 체크 + 증분 인덱싱

- **정합성 체크**
  - 입력: `load_posts()` 결과의 게시글 수/ID 집합
  - 비교: Chroma `posts_oai` count 및(가능하면) ID 존재 여부
  - 정책: 불일치 시 재인덱싱/경고만 표시 등 운영 정책 결정
- **증분 인덱싱**
  - `post_id`별로 “본문/첨부 파싱 결과” 기반 해시를 저장하고 변경분만 upsert.
  - `enrich_posts_with_files()`는 캐시/스킵 로직을 추가해 불필요한 첨부 재파싱을 줄임.

#### Phase 3 (P1) - Agent 안정화(세션/동시성/툴콜 방어)

- **세션 TTL/LRU + windowing**
  - `_sessions`에 만료/최대 보관량 적용, 세션별 최근 N턴만 유지.
- **툴 arguments 파싱 방어**
  - `json.loads()` 실패 시에도 서비스가 죽지 않게 에러 결과로 처리하고 루프 지속.

#### Phase 4 (옵션) - “시그연합회” 전환 대응

- **보드/데이터 소스 설정화**
  - 크롤러 `BOARD_URL`/`bo_table` 및 로더의 입력 JSON을 env로 분리.
  - 프롬프트/프론트 초기 안내문도 동일 설정으로 전환 가능하게 구성.

#### Phase 5 (중기) - 운영/문서/보안 정리

- **S3 sync 범위 분리**
  - 원본 데이터(JSON/files)와 런타임 산출물(chroma/memory/manifest)을 분리해 덮어쓰기 위험 제거.
- **CORS allowlist**
  - 배포 환경에서 env 기반 허용 목록으로 제한.
- **문서 싱크**
  - 실제 실행법/파일 구조에 맞게 README 갱신.
