import { useState, type ReactElement } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { strategyApi } from "../services/api";
import type { StrategyComparisonData } from "../types";
import { Loading, ErrorBanner, EmptyState } from "../components/LoadingError";

const LABELS: Record<string, string> = { cheapest: "Cheapest", most_on_time: "Most On-Time", most_robust: "Most Robust" };

export default function StrategyComparison() {
  const [data, setData] = useState<StrategyComparisonData | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);

  const run = () => {
    setLoading(true);
    setError(null);
    strategyApi.compare(45)
      .then(setData)
      .catch((e) => setError({ message: e.message, suggestion: e.suggestion }))
      .finally(() => setLoading(false));
  };

  return (
    <div className="space-y-6">
      <div className="neu-raised-sm flex flex-wrap items-center justify-between gap-4 px-5 py-4">
        <p className="text-sm text-muted">Run all three strategies and compare real solver output.</p>
        <button onClick={run} disabled={loading} className="neu-btn-primary px-5 py-3 text-sm font-semibold">
          {loading ? "Running all 3 strategies..." : "Run Comparison"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} suggestion={error.suggestion} />}
      {loading && <Loading label="Solving Cheapest, Most On-Time, and Most Robust..." />}

      {data && !loading && (
        <>
          <div className="neu-raised border-l-4 border-success p-6">
            <p className="mb-1 text-xs font-bold uppercase tracking-wide text-success">Recommended Strategy</p>
            <p className="text-2xl font-bold text-ink">{data.recommendation.recommended_strategy_label}</p>
            <ul className="mt-2 space-y-1">
              {data.recommendation.reasons.map((r, i) => (
                <li key={i} className="text-sm text-muted">- {r}</li>
              ))}
            </ul>
          </div>

          <div className="neu-raised neu-scroll overflow-x-auto p-2">
            <table className="min-w-full text-sm">
              <thead>
                <tr>
                  {["Strategy", "Total Cost", "Overtime", "Penalties", "Changeover", "Late Orders", "On-Time %", "Avg Tardiness", "Utilization", "Robustness"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-dark-shadow/15">
                {data.comparison.map((row) => (
                  <tr key={row.strategy} className={row.strategy === data.recommendation.recommended_strategy ? "bg-success/10" : ""}>
                    <td className="px-4 py-3 font-bold text-ink">{row.strategy_label}</td>
                    <td className="px-4 py-3 text-ink">Rs.{row.total_cost.toLocaleString()}</td>
                    <td className="px-4 py-3 text-ink">Rs.{row.overtime_cost.toLocaleString()}</td>
                    <td className="px-4 py-3 text-ink">Rs.{row.penalty_cost.toLocaleString()}</td>
                    <td className="px-4 py-3 text-ink">Rs.{row.changeover_cost.toLocaleString()}</td>
                    <td className="px-4 py-3 text-ink">{row.late_orders}</td>
                    <td className="px-4 py-3 text-ink">{row.on_time_percentage}%</td>
                    <td className="px-4 py-3 text-ink">{row.average_tardiness_hours}h</td>
                    <td className="px-4 py-3 text-ink">{row.average_machine_utilization_pct}%</td>
                    <td className="px-4 py-3 text-ink">{row.robustness_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ChartCard title="Total Cost by Strategy">
              <BarChart data={data.comparison.map((r) => ({ name: LABELS[r.strategy], value: r.total_cost }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#C5CED9" />
                <XAxis dataKey="name" stroke="#667085" fontSize={12} />
                <YAxis stroke="#667085" fontSize={12} />
                <Tooltip formatter={(v: any) => `Rs.${Number(v).toLocaleString()}`} contentStyle={{ borderRadius: 12, border: "none", boxShadow: "4px 4px 10px #C5CED9" }} />
                <Bar dataKey="value" fill="#4F7CFF" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ChartCard>
            <ChartCard title="On-Time % by Strategy">
              <BarChart data={data.comparison.map((r) => ({ name: LABELS[r.strategy], value: r.on_time_percentage }))}>
                <CartesianGrid strokeDasharray="3 3" stroke="#C5CED9" />
                <XAxis dataKey="name" stroke="#667085" fontSize={12} />
                <YAxis domain={[0, 100]} stroke="#667085" fontSize={12} />
                <Tooltip formatter={(v: any) => `${v}%`} contentStyle={{ borderRadius: 12, border: "none", boxShadow: "4px 4px 10px #C5CED9" }} />
                <Bar dataKey="value" fill="#36B37E" radius={[8, 8, 0, 0]} />
              </BarChart>
            </ChartCard>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <EmptyState title="No comparison run yet" message='Click "Run Comparison" to solve all three strategies and see real results here.' />
      )}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactElement }) {
  return (
    <div className="neu-raised p-5">
      <p className="mb-2 text-sm font-semibold text-ink">{title}</p>
      <ResponsiveContainer width="100%" height={260}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}
