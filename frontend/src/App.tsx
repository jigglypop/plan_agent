import { useState, useEffect, useCallback } from "react";
import {
  FileText,
  Files,
  BarChart3,
  LayoutDashboard,
  MessageSquare,
  Database,
  Menu,
  X,
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

const NAV: { id: Tab; icon: typeof LayoutDashboard; label: string }[] = [
  { id: "chat", icon: MessageSquare, label: "AI 채팅" },
  { id: "dashboard", icon: LayoutDashboard, label: "대시보드" },
];

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>("chat");
  const [sidebarOpen, setSidebarOpen] = useState(false);
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

  const switchTab = (tab: Tab) => {
    setActiveTab(tab);
    setSidebarOpen(false);
  };

  const yearlyData = stats
    ? Object.entries(stats.by_year).map(([year, count]) => ({ month: year, count }))
    : [];

  const authorData = stats
    ? Object.entries(stats.by_author).slice(0, 10).map(([name, count]) => ({ name, count }))
    : [];

  return (
    <div className="h-screen flex overflow-hidden">
      {/* Sidebar overlay (mobile) */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 bg-black/60 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`fixed lg:static inset-y-0 left-0 z-50 w-64 bg-black/60 backdrop-blur-2xl border-r border-white/10 flex flex-col transition-transform duration-200 lg:translate-x-0 ${
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        }`}
      >
        {/* Logo */}
        <div className="px-5 py-5 border-b border-white/5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-lg font-bold text-white tracking-tight">염시코기 2세</h1>
              <p className="text-[11px] text-slate-500 mt-0.5">기획위원장 과로사 방지 AI Agent</p>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden p-1 text-slate-400 hover:text-white"
            >
              <X size={18} />
            </button>
          </div>
        </div>

        {/* Nav */}
        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ id, icon: Icon, label }) => (
            <button
              key={id}
              onClick={() => switchTab(id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                activeTab === id
                  ? "bg-white/10 text-white"
                  : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
              }`}
            >
              <Icon size={18} />
              {label}
            </button>
          ))}
        </nav>

        {/* Status */}
        <div className="px-5 py-4 border-t border-white/5">
          {stats ? (
            <div className="flex items-center gap-2 text-xs text-slate-500">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
              {stats.total_posts}건 / {stats.total_files}개 파일
            </div>
          ) : (
            <div className="text-xs text-slate-600">연결 중...</div>
          )}
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 border-b border-white/5">
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-1.5 text-slate-400 hover:text-white rounded-lg hover:bg-white/5"
          >
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold text-white">
            {NAV.find((n) => n.id === activeTab)?.label}
          </span>
        </div>

        {/* Content */}
        {activeTab === "chat" && <ChatPanel />}

        {activeTab === "dashboard" && (
          <main className="flex-1 overflow-y-auto px-4 sm:px-8 py-6 sm:py-8">
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

              {!loading && !error && stats && dashboard && (
                <div className="space-y-8 animate-fade-in">
                  <div className="grid grid-cols-2 lg:grid-cols-4 gap-5">
                    <StatCard icon={<FileText size={24} />} value={stats.total_posts} label="총 게시글" color="blue" />
                    <StatCard icon={<Files size={24} />} value={stats.total_files} label="총 첨부파일" color="green" />
                    <StatCard icon={<BarChart3 size={24} />} value={stats.year_range} label="데이터 기간" color="amber" />
                    <StatCard icon={<Database size={24} />} value={dashboard.vectordb_stats.posts} label="벡터 인덱스" color="purple" />
                  </div>
                  <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">
                    <RecentPosts posts={dashboard.recent_posts} />
                    <MonthlyChart data={yearlyData} title="연도별 게시글" />
                    <ManagerChart data={authorData} title="작성자 TOP 10" />
                  </div>
                </div>
              )}
            </div>
          </main>
        )}
      </div>
    </div>
  );
}
