import type { ReactNode } from "react";

interface StatCardProps {
  icon: ReactNode;
  value: string | number;
  label: string;
  color: "blue" | "green" | "yellow" | "red";
}

export function StatCard({ icon, value, label, color }: StatCardProps) {
  return (
    <div className="card stat-card">
      <div className={`stat-icon ${color}`}>{icon}</div>
      <div className="stat-content">
        <div className="stat-value">{value}</div>
        <div className="stat-label">{label}</div>
      </div>
    </div>
  );
}
