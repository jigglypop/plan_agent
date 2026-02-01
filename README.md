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
