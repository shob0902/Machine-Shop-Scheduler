import { useEffect, useState } from "react";
import { PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend } from "recharts";
import { costApi } from "../services/api";
import type { CostBreakdown } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { Loading, ErrorBanner } from "../components/LoadingError";
import StatCard from "../components/StatCard";

const COLORS = ["#2563eb", "#dc2626", "#f59e0b", "#7c3aed", "#6b7280"];

export default function CostAnalysis() {
  const { strategy, refreshKey } = useStrategy();
  const [cost, setCost] = useState<CostBreakdown | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);

  useEffect(() => {
    setLoading(true);
    costApi.get(strategy)
      .then(setCost)
      .catch((e) => setError({ message: e.message, suggestion: e.suggestion }))
      .finally(() => setLoading(false));
  }, [strategy, refreshKey]);

  if (loading) return <Loading label="Loading cost breakdown..." />;
  if (error) return <ErrorBanner message={error.message} suggestion={error.suggestion} />;
  if (!cost) return null;

  const pieData = [
    { name: "Operating", value: cost.operating_cost },
    { name: "Overtime", value: cost.overtime_cost },
    { name: "Penalties", value: cost.penalty_cost },
    { name: "Changeover", value: cost.changeover_cost },
    { name: "Other Disruption", value: cost.other_disruption_cost },
  ].filter((d) => d.value > 0);

  return (
    <div className="space-y-6">
      <h1 className="text-3xl font-bold text-gray-900">Cost Analysis</h1>

      <div className="grid grid-cols-2 gap-4 md:grid-cols-3">
        <StatCard label="Operating Cost" value={`Rs.${cost.operating_cost.toLocaleString()}`} />
        <StatCard label="Overtime Cost" value={`Rs.${cost.overtime_cost.toLocaleString()}`} tone={cost.overtime_cost > 0 ? "warn" : "good"} />
        <StatCard label="Late Penalties" value={`Rs.${cost.penalty_cost.toLocaleString()}`} tone={cost.penalty_cost > 0 ? "bad" : "good"} />
        <StatCard label="Changeover Cost" value={`Rs.${cost.changeover_cost.toLocaleString()}`} sub={`${cost.wasted_changeover_minutes} min`} />
        <StatCard label="Other Disruption Cost" value={`Rs.${cost.other_disruption_cost.toLocaleString()}`} />
        <StatCard label="Total Cost" value={`Rs.${cost.total_cost.toLocaleString()}`} />
      </div>

      <div className="rounded-2xl border border-gray-200 bg-white p-4">
        <p className="mb-2 font-semibold text-gray-700">Cost Breakdown</p>
        <ResponsiveContainer width="100%" height={320}>
          <PieChart>
            <Pie data={pieData} dataKey="value" nameKey="name" cx="50%" cy="50%" outerRadius={110} label>
              {pieData.map((_, i) => <Cell key={i} fill={COLORS[i % COLORS.length]} />)}
            </Pie>
            <Tooltip formatter={(v: any) => `Rs.${Number(v).toLocaleString()}`} />
            <Legend />
          </PieChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
