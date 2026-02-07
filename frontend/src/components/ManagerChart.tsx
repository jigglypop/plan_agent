import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";

interface ManagerChartProps {
  data: { name: string; count: number }[];
  title?: string;
}

export function ManagerChart({ data, title = "작성자별 게시글" }: ManagerChartProps) {
  return (
    <div className="glass-dark p-5">
      <div className="mb-4">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{title}</span>
      </div>
      <div className="h-64">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.05)" />
            <XAxis type="number" tick={{ fontSize: 11, fill: "#94a3b8" }} axisLine={false} tickLine={false} />
            <YAxis type="category" dataKey="name" tick={{ fontSize: 11, fill: "#94a3b8" }} width={70} axisLine={false} tickLine={false} />
            <Tooltip
              contentStyle={{
                background: "rgba(0,0,0,0.8)",
                border: "1px solid rgba(255,255,255,0.1)",
                borderRadius: 12,
                color: "#e2e8f0",
                fontSize: 13,
              }}
            />
            <Bar dataKey="count" fill="#22c55e" radius={[0, 4, 4, 0]} />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
