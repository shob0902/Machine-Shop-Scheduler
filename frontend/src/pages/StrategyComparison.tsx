import { useState } from "react";
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from "recharts";
import { strategyApi } from "../services/api";
import type { StrategyComparisonData } from "../types";
import { Loading, ErrorBanner } from "../components/LoadingError";

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
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Strategy Comparison</h1>
          <p className="text-gray-500">Run all three strategies and compare real solver output.</p>
        </div>
        <button
          onClick={run}
          disabled={loading}
          className="rounded-xl bg-blue-600 px-5 py-3 text-lg font-semibold text-white shadow hover:bg-blue-700 disabled:opacity-50"
        >
          {loading ? "Running all 3 strategies..." : "Run Comparison"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} suggestion={error.suggestion} />}
      {loading && <Loading label="Solving Cheapest, Most On-Time, and Most Robust..." />}

      {data && !loading && (
        <>
          <div className="rounded-2xl border-2 border-green-400 bg-green-50 p-6">
            <p className="mb-1 text-sm font-bold uppercase tracking-wide text-green-700">Recommended Strategy</p>
            <p className="text-2xl font-bold text-green-900">{data.recommendation.recommended_strategy_label}</p>
            <ul className="mt-2 space-y-1">
              {data.recommendation.reasons.map((r, i) => (
                <li key={i} className="text-sm text-green-800">- {r}</li>
              ))}
            </ul>
          </div>

          <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  {["Strategy", "Total Cost", "Overtime", "Penalties", "Changeover", "Late Orders", "On-Time %", "Avg Tardiness", "Utilization", "Robustness"].map((h) => (
                    <th key={h} className="px-4 py-3 text-left font-semibold text-gray-600">{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {data.comparison.map((row) => (
                  <tr key={row.strategy} className={row.strategy === data.recommendation.recommended_strategy ? "bg-green-50" : ""}>
                    <td className="px-4 py-3 font-bold">{row.strategy_label}</td>
                    <td className="px-4 py-3">Rs.{row.total_cost.toLocaleString()}</td>
                    <td className="px-4 py-3">Rs.{row.overtime_cost.toLocaleString()}</td>
                    <td className="px-4 py-3">Rs.{row.penalty_cost.toLocaleString()}</td>
                    <td className="px-4 py-3">Rs.{row.changeover_cost.toLocaleString()}</td>
                    <td className="px-4 py-3">{row.late_orders}</td>
                    <td className="px-4 py-3">{row.on_time_percentage}%</td>
                    <td className="px-4 py-3">{row.average_tardiness_hours}h</td>
                    <td className="px-4 py-3">{row.average_machine_utilization_pct}%</td>
                    <td className="px-4 py-3">{row.robustness_score}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-4 md:grid-cols-2">
            <ChartCard title="Total Cost by Strategy">
              <BarChart data={data.comparison.map((r) => ({ name: LABELS[r.strategy], value: r.total_cost }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis />
                <Tooltip formatter={(v: any) => `Rs.${Number(v).toLocaleString()}`} />
                <Bar dataKey="value" fill="#2563eb" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ChartCard>
            <ChartCard title="On-Time % by Strategy">
              <BarChart data={data.comparison.map((r) => ({ name: LABELS[r.strategy], value: r.on_time_percentage }))}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={(v: any) => `${v}%`} />
                <Bar dataKey="value" fill="#16a34a" radius={[6, 6, 0, 0]} />
              </BarChart>
            </ChartCard>
          </div>
        </>
      )}

      {!data && !loading && !error && (
        <div className="rounded-2xl border border-dashed border-gray-300 bg-white p-10 text-center text-gray-500">
          Click "Run Comparison" to solve all three strategies and see real results here.
        </div>
      )}
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: React.ReactElement }) {
  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <p className="mb-2 font-semibold text-gray-700">{title}</p>
      <ResponsiveContainer width="100%" height={260}>
        {children}
      </ResponsiveContainer>
    </div>
  );
}
