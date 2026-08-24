import { useEffect, useState } from "react";
import { dashboardApi, scheduleApi } from "../services/api";
import type { DashboardData } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { Loading, ErrorBanner } from "../components/LoadingError";
import StatCard from "../components/StatCard";

export default function Dashboard() {
  const { strategy, refreshKey } = useStrategy();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    dashboardApi.get(strategy)
      .then(setData)
      .catch((e) => setError({ message: e.message, suggestion: e.suggestion }))
      .finally(() => setLoading(false));
  };

  useEffect(load, [strategy, refreshKey]);

  const handleGenerate = async () => {
    setGenerating(true);
    setError(null);
    try {
      await scheduleApi.generate(strategy, 60, false);
      load();
    } catch (e: any) {
      setError({ message: e.message, suggestion: e.suggestion });
    } finally {
      setGenerating(false);
    }
  };

  if (loading) return <Loading label="Loading dashboard..." />;

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold text-gray-900">Supervisor Dashboard</h1>
          <p className="text-gray-500">Two-week production plan at a glance.</p>
        </div>
        <button
          onClick={handleGenerate}
          disabled={generating}
          className="rounded-xl bg-blue-600 px-5 py-3 text-lg font-semibold text-white shadow hover:bg-blue-700 disabled:opacity-50"
        >
          {generating ? "Generating..." : "Regenerate Schedule"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} suggestion={error.suggestion} />}

      {data && (
        <>
          {data.critical_alerts.length > 0 && (
            <div className="rounded-2xl border-2 border-red-300 bg-red-50 p-5">
              <p className="mb-2 text-lg font-bold text-red-800">Action Needed</p>
              <ul className="space-y-1">
                {data.critical_alerts.map((a, i) => (
                  <li key={i} className={`text-base ${a.level === "critical" ? "text-red-800 font-semibold" : "text-yellow-800"}`}>
                    {a.icon === "red" && "\u{1F534} "}
                    {a.icon === "black" && "\u{26AB} "}
                    {a.icon === "yellow" && "\u{1F7E1} "}
                    {a.message}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
            <StatCard label="Total Orders" value={String(data.total_orders)} />
            <StatCard
              label="On-Time %"
              value={`${data.on_time_percentage}%`}
              tone={data.on_time_percentage >= 90 ? "good" : data.on_time_percentage >= 70 ? "warn" : "bad"}
            />
            <StatCard label="Late Orders" value={String(data.late_orders)} tone={data.late_orders > 0 ? "bad" : "good"} />
            <StatCard label="At Risk Orders" value={String(data.at_risk_orders)} tone={data.at_risk_orders > 0 ? "warn" : "good"} />
            <StatCard label="Avg Machine Utilization" value={`${data.average_machine_utilization_pct}%`} />
            <StatCard label="Peak Machine Utilization" value={`${data.peak_machine_utilization_pct}%`} />
            <StatCard label="Overtime Hours" value={`${data.overtime_hours}h`} />
            <StatCard label="Total Cost" value={`Rs.${data.total_cost.toLocaleString()}`} />
          </div>

          <div className="rounded-2xl border border-gray-200 bg-white p-5">
            <p className="mb-3 text-lg font-bold text-gray-900">Recent Disruptions</p>
            {data.recent_disruptions.length === 0 ? (
              <p className="text-gray-500">No disruptions recorded yet.</p>
            ) : (
              <ul className="divide-y divide-gray-100">
                {data.recent_disruptions.map((d) => (
                  <li key={d.id} className="flex items-center justify-between py-2">
                    <span className="font-medium text-gray-800">{d.disruption_type.replace(/_/g, " ")}</span>
                    <span className="text-sm text-gray-500">{new Date(d.created_at).toLocaleString()}</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
}
