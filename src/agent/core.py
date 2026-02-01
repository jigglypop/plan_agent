"""
AI 에이전트 코어
자연어 명령을 처리하고 적절한 액션을 실행
"""
import os
import json
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta

try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    OpenAI = None

from src.crawler import DummyCrawler
from src.stats import StatsAnalyzer
from src.pm import PMManager
from src.notion import NotionClient


SYSTEM_PROMPT = """당신은 기획위원회의 AI PM 어시스턴트입니다.
행사 관리, 통계 분석, 태스크 관리를 도와줍니다.

사용자의 요청을 분석하고 적절한 함수를 호출하세요.

가능한 작업:
1. 통계 조회 (행사 수, 참석자, 예산, 참석률 등)
2. 행사 목록 조회 (다가오는 행사, 완료된 행사 등)
3. 태스크 조회 (기한 초과, 담당자별 등)
4. 리포트 생성 (주간, 월간)
5. 행사 생성 (노션에 새 행사 추가)
6. 리마인더 조회

응답은 친근하고 간결하게 작성하세요.
통계는 핵심 수치 위주로 요약하세요.
"""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_stats_summary",
            "description": "전체 통계 요약을 조회합니다",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_events",
            "description": "다가오는 행사 목록을 조회합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "며칠 이내의 행사를 조회할지 (기본 30일)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_events_by_month",
            "description": "특정 월의 행사를 조회합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "year": {"type": "integer", "description": "연도"},
                    "month": {"type": "integer", "description": "월 (1-12)"}
                },
                "required": ["year", "month"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_overdue_tasks",
            "description": "기한이 지난 태스크를 조회합니다",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks_by_assignee",
            "description": "특정 담당자의 태스크를 조회합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "assignee": {"type": "string", "description": "담당자 이름"}
                },
                "required": ["assignee"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_weekly_report",
            "description": "주간 리포트를 생성합니다",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_reminders",
            "description": "다가오는 행사 리마인더를 조회합니다",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_category_stats",
            "description": "카테고리별 행사 통계를 조회합니다",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_manager_stats",
            "description": "담당자별 행사 통계를 조회합니다",
            "parameters": {"type": "object", "properties": {}, "required": []}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "create_event",
            "description": "새 행사를 생성합니다",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "행사 제목"},
                    "date": {"type": "string", "description": "행사 날짜 (YYYY-MM-DD)"},
                    "location": {"type": "string", "description": "장소"},
                    "budget": {"type": "integer", "description": "예산 (원)"},
                    "manager": {"type": "string", "description": "담당자"},
                    "category": {"type": "string", "description": "카테고리 (세미나, 워크샵, 컨퍼런스 등)"}
                },
                "required": ["title", "date"]
            }
        }
    }
]


class Agent:
    """AI 에이전트"""
    
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.client = None
        
        if OPENAI_AVAILABLE and self.api_key:
            self.client = OpenAI(api_key=self.api_key)
        
        # 데이터 로드
        self.crawler = DummyCrawler()
        self.events = self.crawler.fetch_events()
        self.tasks = self.crawler.fetch_tasks()
        self.budget_items = self.crawler.fetch_budget_items()
        self.attendees = self.crawler.fetch_attendees()
        
        # 분석 도구
        self.stats = StatsAnalyzer(self.events, self.tasks, self.budget_items, self.attendees)
        self.pm = PMManager(self.events, self.tasks)
        
        # 노션 클라이언트
        self.notion = NotionClient()
        
        # 대화 기록
        self.messages = []
    
    def is_ready(self) -> Dict[str, bool]:
        """연결 상태 확인"""
        return {
            "openai": self.client is not None,
            "notion": self.notion.is_connected(),
            "data_loaded": len(self.events) > 0
        }
    
    def reset_conversation(self):
        """대화 초기화"""
        self.messages = []
    
    def chat(self, user_message: str) -> str:
        """사용자 메시지 처리"""
        if not self.client:
            return self._fallback_response(user_message)
        
        self.messages.append({"role": "user", "content": user_message})
        
        try:
            response = self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages,
                tools=TOOLS,
                tool_choice="auto"
            )
            
            assistant_message = response.choices[0].message
            
            # 함수 호출 처리
            if assistant_message.tool_calls:
                tool_results = []
                for tool_call in assistant_message.tool_calls:
                    result = self._execute_function(
                        tool_call.function.name,
                        json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                    )
                    tool_results.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "content": json.dumps(result, ensure_ascii=False, default=str)
                    })
                
                # 함수 결과로 다시 응답 생성
                self.messages.append(assistant_message)
                self.messages.extend(tool_results)
                
                final_response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[{"role": "system", "content": SYSTEM_PROMPT}] + self.messages
                )
                
                final_content = final_response.choices[0].message.content
                self.messages.append({"role": "assistant", "content": final_content})
                return final_content
            else:
                content = assistant_message.content
                self.messages.append({"role": "assistant", "content": content})
                return content
                
        except Exception as e:
            return f"오류가 발생했습니다: {str(e)}"
    
    def _execute_function(self, name: str, args: Dict) -> Any:
        """함수 실행"""
        if name == "get_stats_summary":
            return self.stats.generate_summary()
        
        elif name == "get_upcoming_events":
            days = args.get("days", 30)
            events = self.pm.get_upcoming_events(days)
            return [
                {
                    "title": e.title,
                    "date": e.start_date.strftime("%Y-%m-%d"),
                    "location": e.location,
                    "manager": e.manager,
                    "expected_attendees": e.expected_attendees
                }
                for e in events[:10]
            ]
        
        elif name == "get_events_by_month":
            year = args["year"]
            month = args["month"]
            filtered = [
                e for e in self.events
                if e.start_date.year == year and e.start_date.month == month
            ]
            return [
                {
                    "title": e.title,
                    "date": e.start_date.strftime("%Y-%m-%d"),
                    "status": e.status.value,
                    "location": e.location
                }
                for e in filtered
            ]
        
        elif name == "get_overdue_tasks":
            tasks = self.pm.get_overdue_tasks()
            return [
                {
                    "title": t.title,
                    "assignee": t.assignee,
                    "due_date": t.due_date.strftime("%Y-%m-%d"),
                    "priority": t.priority
                }
                for t in tasks[:10]
            ]
        
        elif name == "get_tasks_by_assignee":
            assignee = args["assignee"]
            tasks = self.pm.get_tasks_by_assignee(assignee)
            return [
                {
                    "title": t.title,
                    "status": t.status.value,
                    "due_date": t.due_date.strftime("%Y-%m-%d"),
                    "priority": t.priority
                }
                for t in tasks[:10]
            ]
        
        elif name == "get_weekly_report":
            return self.pm.generate_weekly_report()
        
        elif name == "get_reminders":
            reminders = self.pm.generate_reminders()
            return [
                {
                    "event": r.event_title,
                    "days_until": r.days_until,
                    "message": r.message,
                    "priority": r.priority
                }
                for r in reminders[:10]
            ]
        
        elif name == "get_category_stats":
            return self.stats.events_by_category()
        
        elif name == "get_manager_stats":
            return self.stats.events_by_manager()
        
        elif name == "create_event":
            # 노션에 행사 생성 (데이터베이스 ID 필요)
            return {
                "status": "pending",
                "message": "노션 데이터베이스 ID가 설정되지 않았습니다. .env에 NOTION_DATABASE_ID를 추가해주세요.",
                "event_data": args
            }
        
        return {"error": f"Unknown function: {name}"}
    
    def _fallback_response(self, message: str) -> str:
        """GPT 없이 기본 응답"""
        message_lower = message.lower()
        
        if "통계" in message or "현황" in message:
            summary = self.stats.generate_summary()
            return f"""통계 요약:
- 총 행사: {summary['overview']['total_events']}건
- 총 참석자: {summary['overview']['total_attendees']:,}명
- 총 예산: {summary['overview']['total_budget']:,}원
- 평균 참석률: {summary['performance']['average_attendance_rate']}%
- 태스크 완료율: {summary['performance']['task_completion_rate']}%"""
        
        elif "다가오는" in message or "예정" in message or "다음" in message:
            events = self.pm.get_upcoming_events(30)
            if not events:
                return "다가오는 행사가 없습니다."
            result = "다가오는 행사:\n"
            for e in events[:5]:
                result += f"- {e.title} ({e.start_date.strftime('%m/%d')}) @ {e.location}\n"
            return result
        
        elif "기한" in message or "마감" in message or "초과" in message:
            tasks = self.pm.get_overdue_tasks()
            if not tasks:
                return "기한 초과된 태스크가 없습니다."
            result = f"기한 초과 태스크 ({len(tasks)}건):\n"
            for t in tasks[:5]:
                result += f"- {t.title} (담당: {t.assignee}, 마감: {t.due_date.strftime('%m/%d')})\n"
            return result
        
        elif "리포트" in message or "보고서" in message:
            report = self.pm.generate_weekly_report()
            return f"""주간 리포트 ({report['period']}):
- 완료 행사: {report['completed_events']}건
- 예정 행사: {report['upcoming_events']}건
- 대기 태스크: {report['pending_tasks']}건
- 기한 초과: {report['overdue_tasks']}건"""
        
        else:
            return """가능한 명령:
- "통계 알려줘" - 전체 통계 조회
- "다가오는 행사" - 예정 행사 목록
- "기한 초과 태스크" - 마감 지난 태스크
- "주간 리포트" - 주간 보고서 생성

GPT 연동 시 더 자연스러운 대화가 가능합니다."""
