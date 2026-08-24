import { useEffect, useState } from "react";
import { machineApi } from "../services/api";
import type { Machine } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { Loading, ErrorBanner } from "../components/LoadingError";

export default function Machines() {
  const { strategy, refreshKey } = useStrategy();
  const [machines, setMachines] = useState<Machine[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);

  useEffect(() => {
    setLoading(true);
    machineApi.list(strategy)
      .then(setMachines)
      .catch((e) => setError({ message: e.message, suggestion: e.suggestion }))
      .finally(() => setLoading(false));
  }, [strategy, refreshKey]);

  if (loading) return <Loading label="Loading machines..." />;
  if (error) return <ErrorBanner message={error.message} suggestion={error.suggestion} />;

  return (
    <div className="space-y-4">
      <h1 className="text-3xl font-bold text-gray-900">Machines</h1>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {machines.map((m) => (
          <div key={m.machine_id} className="rounded-2xl border border-gray-200 bg-white p-5">
            <div className="mb-2 flex items-start justify-between">
              <div>
                <p className="text-lg font-bold text-gray-900">{m.machine_name}</p>
                <p className="text-sm text-gray-500">{m.machine_id} - {m.machine_type}</p>
              </div>
              <span className={`rounded-full px-2 py-1 text-xs font-semibold ${m.status === "down" ? "bg-black text-white" : "bg-green-100 text-green-800"}`}>
                {m.status === "down" ? "DOWN" : "OK"}
              </span>
            </div>
            <div className="mb-3">
              <div className="mb-1 flex justify-between text-xs text-gray-500">
                <span>Utilization</span>
                <span>{m.utilization?.utilization_pct ?? 0}%</span>
              </div>
              <div className="h-2 w-full rounded-full bg-gray-100">
                <div
                  className={`h-2 rounded-full ${(m.utilization?.utilization_pct ?? 0) > 85 ? "bg-red-500" : "bg-blue-500"}`}
                  style={{ width: `${Math.min(100, m.utilization?.utilization_pct ?? 0)}%` }}
                />
              </div>
            </div>
            <dl className="space-y-1 text-sm">
              <div className="flex justify-between"><dt className="text-gray-500">Current job</dt><dd>{m.current_operation ? m.current_operation.order_id : "idle"}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Next job</dt><dd>{m.next_operation ? m.next_operation.order_id : "-"}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Breakdowns (history)</dt><dd>{m.reliability.breakdown_count}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">MTBF</dt><dd>{m.reliability.mtbf_hours ? `${m.reliability.mtbf_hours}h` : "-"}</dd></div>
              <div className="flex justify-between"><dt className="text-gray-500">Maintenance windows</dt><dd>{m.maintenance_windows.length}</dd></div>
            </dl>
          </div>
        ))}
      </div>
    </div>
  );
}
