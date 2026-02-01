"""
Plan Agent - 메인 실행 파일
"""
import json
from src.crawler import DummyCrawler
from src.stats import StatsAnalyzer
from src.pm import PMManager


def main():
    print("=" * 60)
    print("Plan Agent - AI 기반 기획위원회 PM/통계 시스템")
    print("=" * 60)
    
    # 1. 데이터 로드 (현재 더미)
    print("\n[1] 데이터 로드 중...")
    crawler = DummyCrawler()
    events = crawler.fetch_events()
    tasks = crawler.fetch_tasks()
    budget_items = crawler.fetch_budget_items()
    attendees = crawler.fetch_attendees()
    
    print(f"    - 행사: {len(events)}건")
    print(f"    - 태스크: {len(tasks)}건")
    print(f"    - 예산항목: {len(budget_items)}건")
    print(f"    - 참석자: {len(attendees)}명")
    
    # 2. 통계 분석
    print("\n[2] 통계 분석...")
    analyzer = StatsAnalyzer(events, tasks, budget_items, attendees)
    summary = analyzer.generate_summary()
    
    print("\n--- 개요 ---")
    print(f"    총 행사: {summary['overview']['total_events']}건")
    print(f"    총 참석자: {summary['overview']['total_attendees']:,}명")
    print(f"    총 예산: {summary['overview']['total_budget']:,}원")
    print(f"    실제 비용: {summary['overview']['total_actual_cost']:,}원")
    
    print("\n--- 성과 지표 ---")
    print(f"    평균 참석률: {summary['performance']['average_attendance_rate']}%")
    print(f"    예산 효율성: {summary['performance']['budget_efficiency']}%")
    print(f"    1인당 비용: {summary['performance']['cost_per_attendee']:,.0f}원")
    print(f"    태스크 완료율: {summary['performance']['task_completion_rate']}%")
    print(f"    평균 만족도: {summary['performance']['average_feedback_score']}/5")
    
    print("\n--- 카테고리별 분포 ---")
    for cat, count in summary['distribution']['by_category'].items():
        print(f"    {cat}: {count}건")
    
    # 3. PM 기능
    print("\n[3] PM 대시보드...")
    pm = PMManager(events, tasks)
    dashboard = pm.get_dashboard_data()
    
    print(f"\n    오늘 행사: {len(dashboard['today_events'])}건")
    print(f"    다가오는 행사 (7일): {len(dashboard['upcoming_events'])}건")
    print(f"    기한 초과 태스크: {dashboard['overdue_tasks']}건")
    print(f"    대기 중 태스크: {dashboard['pending_tasks']}건")
    print(f"    일정 충돌: {dashboard['conflicts_count']}건")
    
    if dashboard['reminders']:
        print("\n--- 리마인더 ---")
        for r in dashboard['reminders'][:3]:
            print(f"    [{r['priority']}] {r['event_title']}: {r['message']}")
    
    print("\n" + "=" * 60)
    print("시스템 준비 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
