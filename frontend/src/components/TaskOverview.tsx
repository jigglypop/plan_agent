import { CheckCircle2, Clock, AlertTriangle } from "lucide-react";
import type { Task } from "../types";

interface TaskOverviewProps {
  tasks: Task[];
  overdueTasks: Task[];
}

export function TaskOverview({ tasks, overdueTasks }: TaskOverviewProps) {
  const total = tasks.length;
  const completed = tasks.filter((t) => t.status === "완료").length;
  const inProgress = tasks.filter((t) => t.status === "진행중").length;
  const pending = tasks.filter((t) => t.status === "할일").length;
  const completionRate = total > 0 ? Math.round((completed / total) * 100) : 0;

  return (
    <div className="card">
      <div className="card-header">
        <span className="card-title">태스크 현황</span>
      </div>

      <div style={{ marginBottom: "1rem" }}>
        <div
          style={{
            display: "flex",
            justifyContent: "space-between",
            marginBottom: "0.5rem",
          }}
        >
          <span style={{ fontSize: "0.875rem", color: "#6b7280" }}>
            완료율
          </span>
          <span style={{ fontSize: "0.875rem", fontWeight: 600 }}>
            {completionRate}%
          </span>
        </div>
        <div className="progress-bar">
          <div
            className="progress-fill"
            style={{ width: `${completionRate}%` }}
          />
        </div>
      </div>

      <div className="list">
        <div className="list-item">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <CheckCircle2 size={18} color="#22c55e" />
            <span>완료</span>
          </div>
          <span style={{ fontWeight: 600 }}>{completed}</span>
        </div>
        <div className="list-item">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Clock size={18} color="#3b82f6" />
            <span>진행중</span>
          </div>
          <span style={{ fontWeight: 600 }}>{inProgress}</span>
        </div>
        <div className="list-item">
          <div style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}>
            <Clock size={18} color="#9ca3af" />
            <span>할일</span>
          </div>
          <span style={{ fontWeight: 600 }}>{pending}</span>
        </div>
        {overdueTasks.length > 0 && (
          <div
            className="list-item"
            style={{ background: "rgba(239, 68, 68, 0.05)" }}
          >
            <div
              style={{ display: "flex", alignItems: "center", gap: "0.5rem" }}
            >
              <AlertTriangle size={18} color="#ef4444" />
              <span style={{ color: "#ef4444" }}>기한 초과</span>
            </div>
            <span style={{ fontWeight: 600, color: "#ef4444" }}>
              {overdueTasks.length}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
