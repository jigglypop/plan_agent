import type { ReactNode } from "react";

interface StatCardProps {
  icon: ReactNode;
  value: string | number;
  label: string;
  color: "blue" | "green" | "amber" | "purple";
}

const colors = {
  blue: "from-blue-500/20 to-blue-600/10 border-blue-500/20 text-blue-400",
  green: "from-emerald-500/20 to-emerald-600/10 border-emerald-500/20 text-emerald-400",
  amber: "from-amber-500/20 to-amber-600/10 border-amber-500/20 text-amber-400",
  purple: "from-purple-500/20 to-purple-600/10 border-purple-500/20 text-purple-400",
};

export function StatCard({ icon, value, label, color }: StatCardProps) {
  return (
    <div className="glass-dark p-5 flex items-start gap-4">
      <div className={`p-2.5 rounded-xl bg-gradient-to-br border ${colors[color]}`}>
        {icon}
      </div>
      <div>
        <div className="text-2xl font-bold text-white leading-tight">{value}</div>
        <div className="text-sm text-slate-400 mt-0.5">{label}</div>
      </div>
    </div>
  );
}
