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
      await scheduleApi.generate(strategy, 30, false);
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
          <p className="text-sm font-medium text-muted">Good shift, supervisor.</p>
          <p className="text-sm text-muted">Here's the two-week production plan at a glance.</p>
        </div>
        <button onClick={handleGenerate} disabled={generating} className="neu-btn-primary px-5 py-3 text-sm font-semibold">
          {generating ? "Generating..." : "Regenerate Schedule"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} suggestion={error.suggestion} />}

      {data && (
        <>
          {data.critical_alerts.length > 0 && (
            <div className="neu-raised border-l-4 border-error p-5">
              <p className="mb-2 text-base font-bold text-ink">Action Needed</p>
              <ul className="space-y-1.5">
                {data.critical_alerts.map((a, i) => (
                  <li key={i} className={`flex items-start gap-2 text-sm ${a.level === "critical" ? "font-semibold text-ink" : "text-muted"}`}>
                    <span className={`mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full ${a.icon === "red" ? "bg-error" : a.icon === "black" ? "bg-ink" : "bg-warning"}`} />
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

          <div className="neu-raised p-5">
            <p className="mb-3 text-base font-bold text-ink">Recent Disruptions</p>
            {data.recent_disruptions.length === 0 ? (
              <p className="text-sm text-muted">No disruptions recorded yet.</p>
            ) : (
              <ul className="divide-y divide-dark-shadow/20">
                {data.recent_disruptions.map((d) => (
                  <li key={d.id} className="flex items-center justify-between py-2.5">
                    <span className="text-sm font-medium text-ink">{d.disruption_type.replace(/_/g, " ")}</span>
                    <span className="text-xs text-muted">{new Date(d.created_at).toLocaleString()}</span>
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
