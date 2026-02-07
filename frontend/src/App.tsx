import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  Files,
  BarChart3,
  LayoutDashboard,
  MessageSquare,
  Database,
} from "lucide-react";
import {
  StatCard,
  MonthlyChart,
  ManagerChart,
  RecentPosts,
  ChatPanel,
} from "./components";
import type { DashboardData, PostStats } from "./api";
import { api } from "./api";
import "./index.css";

type Tab = "dashboard" | "chat";

const TABS: { id: Tab; icon: typeof LayoutDashboard; label: string }[] = [
  { id: "chat", icon: MessageSquare, label: "AI 에이전트" },
  { id: "dashboard", icon: LayoutDashboard, label: "대시보드" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [stats, setStats] = useState<PostStats | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    try {
      setLoading(true);
      setError("");
      const [d, s] = await Promise.all([api.dashboard(), api.stats()]);
      setDashboard(d);
      setStats(s);
    } catch {
      setError("백엔드 서버에 연결할 수 없습니다.");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const yearlyData = stats
    ? Object.entries(stats.by_year).map(([year, count]) => ({ month: year, count }))
    : [];

  const authorData = stats
    ? Object.entries(stats.by_author).slice(0, 10).map(([name, count]) => ({ name, count }))
    : [];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="glass-dark border-b border-white/10 px-4 sm:px-8 py-4 sm:py-5">
        <div className="max-w-7xl mx-auto flex items-center justify-between">
          <div>
            <h1 className="text-xl sm:text-2xl font-bold text-white tracking-tight">Plan Agent</h1>
            <p className="text-xs sm:text-sm text-slate-400 mt-0.5">기획위원회 AI 에이전트</p>
          </div>
          <div className="flex items-center gap-4">
            {stats && (
              <span className="hidden sm:inline-flex items-center gap-2 px-4 py-1.5 rounded-full text-sm font-medium bg-emerald-500/15 text-emerald-300 border border-emerald-500/20">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                {stats.total_posts}건 로드
              </span>
            )}
          </div>
        </div>
      </header>

      {/* Tabs */}
      <nav className="border-b border-white/5 px-4 sm:px-8">
        <div className="max-w-7xl mx-auto flex gap-1 py-2">
          {TABS.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => setActiveTab(id)}
              className={`flex items-center gap-2 px-4 sm:px-5 py-2.5 sm:py-3 rounded-xl text-sm font-medium whitespace-nowrap transition-all duration-200 cursor-pointer select-none ${
                activeTab === id
                  ? "bg-white/10 text-white border border-white/10"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </div>
      </nav>

      {/* Main */}
      <main className="flex-1 px-3 sm:px-8 py-4 sm:py-8">
        <div className="max-w-7xl mx-auto">
          {error && (
            <div className="glass-dark p-5 mb-6 border-red-500/30 text-red-300 text-sm">
              {error}
            </div>
          )}

          {loading && !error && (
            <div className="glass-dark p-16 text-center text-slate-400 text-base">
              로딩 중...
            </div>
          )}

          {!loading && !error && activeTab === "dashboard" && stats && dashboard && (
            <div className="space-y-8 animate-fade-in">
              {/* Stats */}
              <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
                <StatCard icon={<FileText size={24} />} value={stats.total_posts} label="총 게시글" color="blue" />
                <StatCard icon={<Files size={24} />} value={stats.total_files} label="총 첨부파일" color="green" />
                <StatCard icon={<BarChart3 size={24} />} value={stats.year_range} label="데이터 기간" color="amber" />
                <StatCard icon={<Database size={24} />} value={dashboard.vectordb_stats.posts} label="벡터 인덱스" color="purple" />
              </div>

              {/* Charts + Recent */}
              <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                <RecentPosts posts={dashboard.recent_posts} />
                <MonthlyChart data={yearlyData} title="연도별 게시글" />
                <ManagerChart data={authorData} title="작성자 TOP 10" />
              </div>
            </div>
          )}

          {activeTab === "chat" && (
            <div className="max-w-4xl mx-auto animate-fade-in">
              <ChatPanel />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
