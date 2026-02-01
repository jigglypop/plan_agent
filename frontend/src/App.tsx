import { useState, useMemo } from "react";
import {
  Calendar,
  Users,
  DollarSign,
  TrendingUp,
  BarChart3,
  ListTodo,
  LayoutDashboard,
  MessageSquare,
} from "lucide-react";
import {
  StatCard,
  CategoryChart,
  MonthlyChart,
  ReminderList,
  UpcomingEvents,
  TaskOverview,
  EventTable,
  ManagerChart,
  ChatPanel,
} from "./components";
import {
  generateEvents,
  generateTasks,
  calculateStats,
  getCategoryData,
  getMonthlyData,
  getManagerData,
  getUpcomingEvents,
  getReminders,
  getOverdueTasks,
} from "./data/dummy";
import "./index.css";

type Tab = "dashboard" | "stats" | "events" | "tasks" | "chat";

function formatNumber(num: number): string {
  if (num >= 100000000) {
    return (num / 100000000).toFixed(1) + "억";
  }
  if (num >= 10000) {
    return (num / 10000).toFixed(0) + "만";
  }
  return new Intl.NumberFormat("ko-KR").format(num);
}

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("dashboard");

  const { events, tasks, stats, categoryData, monthlyData, managerData } =
    useMemo(() => {
      const events = generateEvents(50);
      const tasks = generateTasks(events);
      const stats = calculateStats(events, tasks);
      const categoryData = getCategoryData(events);
      const monthlyData = getMonthlyData(events);
      const managerData = getManagerData(events);
      return { events, tasks, stats, categoryData, monthlyData, managerData };
    }, []);

  const upcomingEvents = useMemo(
    () => getUpcomingEvents(events, 30),
    [events]
  );
  const reminders = useMemo(() => getReminders(events), [events]);
  const overdueTasks = useMemo(
    () => getOverdueTasks(tasks, events),
    [tasks, events]
  );

  return (
    <div className="app">
      <header className="header">
        <h1>Plan Agent</h1>
        <p>AI 기반 기획위원회 PM/통계 시스템</p>
      </header>

      <main className="main">
        <div className="tabs">
          <button
            className={`tab ${activeTab === "dashboard" ? "active" : ""}`}
            onClick={() => setActiveTab("dashboard")}
          >
            <LayoutDashboard
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            대시보드
          </button>
          <button
            className={`tab ${activeTab === "stats" ? "active" : ""}`}
            onClick={() => setActiveTab("stats")}
          >
            <BarChart3
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            통계
          </button>
          <button
            className={`tab ${activeTab === "events" ? "active" : ""}`}
            onClick={() => setActiveTab("events")}
          >
            <Calendar
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            행사
          </button>
          <button
            className={`tab ${activeTab === "tasks" ? "active" : ""}`}
            onClick={() => setActiveTab("tasks")}
          >
            <ListTodo
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            태스크
          </button>
          <button
            className={`tab ${activeTab === "chat" ? "active" : ""}`}
            onClick={() => setActiveTab("chat")}
          >
            <MessageSquare
              size={16}
              style={{ marginRight: 6, verticalAlign: "middle" }}
            />
            AI 어시스턴트
          </button>
        </div>

        {activeTab === "dashboard" && (
          <>
            <div className="grid grid-4" style={{ marginBottom: "1.5rem" }}>
              <StatCard
                icon={<Calendar size={24} />}
                value={stats.totalEvents}
                label="총 행사"
                color="blue"
              />
              <StatCard
                icon={<Users size={24} />}
                value={formatNumber(stats.totalAttendees)}
                label="총 참석자"
                color="green"
              />
              <StatCard
                icon={<DollarSign size={24} />}
                value={formatNumber(stats.totalBudget) + "원"}
                label="총 예산"
                color="yellow"
              />
              <StatCard
                icon={<TrendingUp size={24} />}
                value={stats.averageAttendanceRate + "%"}
                label="평균 참석률"
                color="blue"
              />
            </div>

            <div className="grid grid-3" style={{ marginBottom: "1.5rem" }}>
              <ReminderList reminders={reminders} />
              <UpcomingEvents events={upcomingEvents} />
              <TaskOverview tasks={tasks} overdueTasks={overdueTasks} />
            </div>

            <EventTable events={events} />
          </>
        )}

        {activeTab === "stats" && (
          <>
            <div className="grid grid-4" style={{ marginBottom: "1.5rem" }}>
              <StatCard
                icon={<TrendingUp size={24} />}
                value={stats.budgetEfficiency + "%"}
                label="예산 효율성"
                color="green"
              />
              <StatCard
                icon={<DollarSign size={24} />}
                value={formatNumber(stats.costPerAttendee) + "원"}
                label="1인당 비용"
                color="yellow"
              />
              <StatCard
                icon={<ListTodo size={24} />}
                value={stats.taskCompletionRate + "%"}
                label="태스크 완료율"
                color="blue"
              />
              <StatCard
                icon={<Users size={24} />}
                value={stats.averageFeedbackScore.toFixed(1) + "/5"}
                label="평균 만족도"
                color="green"
              />
            </div>

            <div className="grid grid-2" style={{ marginBottom: "1.5rem" }}>
              <CategoryChart data={categoryData} />
              <MonthlyChart data={monthlyData} />
            </div>

            <div className="grid grid-2">
              <ManagerChart data={managerData} />
              <div className="card">
                <div className="card-header">
                  <span className="card-title">주요 지표 요약</span>
                </div>
                <div className="list">
                  <div className="list-item">
                    <span>총 행사 수</span>
                    <span style={{ fontWeight: 600 }}>{stats.totalEvents}건</span>
                  </div>
                  <div className="list-item">
                    <span>완료 행사</span>
                    <span style={{ fontWeight: 600 }}>
                      {events.filter((e) => e.status === "완료").length}건
                    </span>
                  </div>
                  <div className="list-item">
                    <span>온라인 행사 비율</span>
                    <span style={{ fontWeight: 600 }}>
                      {Math.round(
                        (events.filter((e) => e.isOnline).length /
                          events.length) *
                          100
                      )}
                      %
                    </span>
                  </div>
                  <div className="list-item">
                    <span>실제 지출</span>
                    <span style={{ fontWeight: 600 }}>
                      {formatNumber(stats.totalActualCost)}원
                    </span>
                  </div>
                  <div className="list-item">
                    <span>예산 절감</span>
                    <span
                      style={{
                        fontWeight: 600,
                        color:
                          stats.totalBudget > stats.totalActualCost
                            ? "#22c55e"
                            : "#ef4444",
                      }}
                    >
                      {formatNumber(stats.totalBudget - stats.totalActualCost)}원
                    </span>
                  </div>
                </div>
              </div>
            </div>
          </>
        )}

        {activeTab === "events" && <EventTable events={events} />}

        {activeTab === "tasks" && (
          <div className="grid grid-2">
            <TaskOverview tasks={tasks} overdueTasks={overdueTasks} />
            <div className="card">
              <div className="card-header">
                <span className="card-title">담당자별 태스크</span>
              </div>
              <div className="list">
                {Array.from(new Set(tasks.map((t) => t.assignee))).map(
                  (assignee) => {
                    const assigneeTasks = tasks.filter(
                      (t) => t.assignee === assignee
                    );
                    const completed = assigneeTasks.filter(
                      (t) => t.status === "완료"
                    ).length;
                    return (
                      <div key={assignee} className="list-item">
                        <div>
                          <div className="list-item-title">{assignee}</div>
                          <div className="list-item-sub">
                            완료 {completed} / 전체 {assigneeTasks.length}
                          </div>
                        </div>
                        <div style={{ width: 100 }}>
                          <div className="progress-bar">
                            <div
                              className="progress-fill"
                              style={{
                                width: `${(completed / assigneeTasks.length) * 100}%`,
                              }}
                            />
                          </div>
                        </div>
                      </div>
                    );
                  }
                )}
              </div>
            </div>
          </div>
        )}

        {activeTab === "chat" && (
          <div style={{ maxWidth: 800, margin: "0 auto" }}>
            <ChatPanel />
          </div>
        )}
      </main>
    </div>
  );
}
