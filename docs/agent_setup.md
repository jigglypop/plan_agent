# AI 에이전트 구축 가이드

## 현재 상태

| 구성요소 | 상태 |
|----------|------|
| 프론트엔드 (React) | 완료 |
| 데이터 스키마 | 완료 |
| 통계 분석 | 완료 |
| PM 기능 | 완료 |
| **백엔드 API** | 미구현 |
| **GPT 연동** | 미구현 |
| **노션 연동** | 미구현 |
| **에이전트 로직** | 미구현 |

---

## 에이전트로 만들기 위해 필요한 것

### 1. 계정/키 (필수)

| 항목 | 발급처 | 용도 | 비용 |
|------|--------|------|------|
| **OpenAI API Key** | platform.openai.com | GPT 사용 | 사용량 기반 |
| **Notion Integration** | notion.so/my-integrations | 노션 연동 | 무료 |

### 2. 선택 사항

| 항목 | 발급처 | 용도 |
|------|--------|------|
| AWS 계정 | aws.amazon.com | 서버 배포 (로컬도 가능) |
| Slack Webhook | api.slack.com | 알림 발송 |
| Discord Webhook | discord.com | 알림 발송 |

---

## 에이전트 기능 구조

```
사용자 입력 (자연어)
    │
    ▼
┌─────────────────────────────────────┐
│           GPT (OpenAI API)          │
│  - 의도 파악                         │
│  - 명령어 추출                       │
│  - 응답 생성                         │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│           에이전트 코어              │
│  - 통계 조회                         │
│  - 행사 관리                         │
│  - 태스크 관리                       │
│  - 리포트 생성                       │
└─────────────────────────────────────┘
    │
    ▼
┌─────────────────────────────────────┐
│           데이터 소스                │
│  - 노션 (읽기/쓰기)                  │
│  - 크롤링 (읽기)                     │
│  - 로컬 DB                          │
└─────────────────────────────────────┘
```

---

## 에이전트가 할 수 있는 것 (예시)

### 자연어 명령 예시

```
"이번 달 행사 통계 알려줘"
→ 월별 통계 조회 + 요약 생성

"다음 주 행사 뭐 있어?"
→ 다가오는 행사 목록 조회

"해커톤 행사 만들어줘. 3월 15일, 대강당, 예산 200만원"
→ 노션에 행사 페이지 자동 생성

"지난 분기 참석률 분석해줘"
→ 통계 분석 + GPT 인사이트 생성

"김철수 담당 태스크 뭐 남았어?"
→ 담당자별 태스크 조회

"이번 주 리포트 만들어줘"
→ 주간 리포트 자동 생성 + 노션에 저장
```

---

## 구현 순서

### Phase 1: 백엔드 API (1단계)
- FastAPI 서버 구축
- REST API 엔드포인트
- 프론트엔드 연동

### Phase 2: 노션 연동 (2단계)
- Notion API 연결
- 데이터베이스 읽기/쓰기
- 페이지 자동 생성

### Phase 3: GPT 연동 (3단계)
- OpenAI API 연결
- 프롬프트 설계
- 의도 파악 로직

### Phase 4: 에이전트 완성 (4단계)
- 자연어 명령 처리
- 자동화 워크플로우
- 알림 시스템

---

## 지금 바로 시작하려면

### Step 1: OpenAI API Key 발급

1. https://platform.openai.com 접속
2. 로그인 (구글 계정 가능)
3. API Keys 메뉴
4. "Create new secret key" 클릭
5. 키 복사 (sk-... 형태)

### Step 2: Notion Integration 생성

1. https://www.notion.so/my-integrations 접속
2. "New integration" 클릭
3. 이름: "Plan Agent"
4. Capabilities: Read, Update, Insert 체크
5. Submit
6. "Internal Integration Token" 복사 (secret_... 형태)

### Step 3: 노션 페이지에 Integration 연결

1. 노션에서 연동할 페이지/데이터베이스 열기
2. 우측 상단 ... 클릭
3. "Connections" → "Plan Agent" 추가

---

## 환경 변수 설정

```env
# .env 파일
OPENAI_API_KEY=sk-xxxxxxxxxxxxxxxxxxxxxxxx
NOTION_TOKEN=secret_xxxxxxxxxxxxxxxxxxxxxxxx
NOTION_DATABASE_ID=xxxxxxxxxxxxxxxxxxxxxxxx
```

---

## 다음 단계 선택

| 옵션 | 설명 | 필요한 것 |
|------|------|-----------|
| A | 백엔드 API 먼저 | 없음 (바로 가능) |
| B | 노션 연동 먼저 | Notion Integration Token |
| C | GPT 연동 먼저 | OpenAI API Key |
| D | 전체 한번에 | 위 두 가지 모두 |

**권장: A (백엔드 API) → B (노션) → C (GPT) 순서**
