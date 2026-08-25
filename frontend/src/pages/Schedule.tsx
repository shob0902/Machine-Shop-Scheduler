import { useEffect, useState } from "react";
import { scheduleApi, machineApi } from "../services/api";
import type { ScheduleResult, Machine } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { Loading, ErrorBanner } from "../components/LoadingError";
import Gantt from "../components/Gantt";

export default function Schedule() {
  const { strategy, refreshKey } = useStrategy();
  const [schedule, setSchedule] = useState<ScheduleResult | null>(null);
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);
  const [dayFilter, setDayFilter] = useState<"all" | number>("all");

  useEffect(() => {
    setLoading(true);
    setError(null);
    Promise.all([scheduleApi.get(strategy), machineApi.list(strategy)])
      .then(([s, m]) => { setSchedule(s); setMachines(m); })
      .catch((e) => setError({ message: e.message, suggestion: e.suggestion }))
      .finally(() => setLoading(false));
  }, [strategy, refreshKey]);

  if (loading) return <Loading label="Loading two-week schedule..." />;
  if (error) return <ErrorBanner message={error.message} suggestion={error.suggestion} />;
  if (!schedule) return null;

  const ops = dayFilter === "all" ? schedule.operations : schedule.operations.filter((o) => o.day_index === dayFilter);

  return (
    <div className="space-y-4">
      <div className="neu-raised-sm flex flex-wrap items-center justify-between gap-3 px-5 py-4">
        <p className="text-sm text-muted">
          {schedule.operations.length} operations across 14 machines &middot; Solver: {schedule.solver_status} ({schedule.solver_wall_time_seconds}s)
        </p>
      </div>

      <div className="neu-inset neu-scroll flex items-center gap-2 overflow-x-auto p-2">
        <button
          onClick={() => setDayFilter("all")}
          className={`shrink-0 rounded-xl px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition-colors ${dayFilter === "all" ? "neu-btn-primary" : "text-muted hover:text-ink"}`}
        >
          All days
        </button>
        {Array.from({ length: 14 }).map((_, d) => (
          <button
            key={d}
            onClick={() => setDayFilter(d)}
            className={`shrink-0 rounded-xl px-3 py-1.5 text-xs font-semibold whitespace-nowrap transition-colors ${dayFilter === d ? "neu-btn-primary" : "text-muted hover:text-ink"}`}
          >
            Day {d + 1}
          </button>
        ))}
      </div>

      <Gantt machines={machines} operations={ops} />
    </div>
  );
}
