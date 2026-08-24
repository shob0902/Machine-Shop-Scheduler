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
      <div>
        <h1 className="text-3xl font-bold text-gray-900">Two-Week Schedule</h1>
        <p className="text-gray-500">
          Machine-by-machine, shift-by-shift. {schedule.operations.length} operations across 14 machines.
          Solver: {schedule.solver_status} ({schedule.solver_wall_time_seconds}s)
        </p>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <button
          onClick={() => setDayFilter("all")}
          className={`rounded-full px-3 py-1 text-sm font-medium ${dayFilter === "all" ? "bg-blue-600 text-white" : "bg-white border border-gray-300 text-gray-700"}`}
        >
          All days
        </button>
        {Array.from({ length: 14 }).map((_, d) => (
          <button
            key={d}
            onClick={() => setDayFilter(d)}
            className={`rounded-full px-3 py-1 text-sm font-medium ${dayFilter === d ? "bg-blue-600 text-white" : "bg-white border border-gray-300 text-gray-700"}`}
          >
            Day {d + 1}
          </button>
        ))}
      </div>

      <Gantt machines={machines} operations={ops} />
    </div>
  );
}
