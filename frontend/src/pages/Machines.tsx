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
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
        {machines.map((m) => {
          const util = m.utilization?.utilization_pct ?? 0;
          return (
            <div key={m.machine_id} className="neu-raised p-5">
              <div className="mb-3 flex items-start justify-between">
                <div>
                  <p className="text-base font-bold text-ink">{m.machine_name}</p>
                  <p className="text-xs text-muted">{m.machine_id} &middot; {m.machine_type}</p>
                </div>
                <span className={`neu-chip ${m.status === "down" ? "bg-ink text-white" : "bg-success/15 text-success"}`}>
                  {m.status === "down" ? "DOWN" : "OK"}
                </span>
              </div>
              <div className="mb-4">
                <div className="mb-1.5 flex justify-between text-xs text-muted">
                  <span>Utilization</span>
                  <span className="font-semibold text-ink">{util}%</span>
                </div>
                <div className="neu-inset-sm h-3 w-full p-0.5">
                  <div
                    className={`h-full rounded-full transition-all ${util > 85 ? "bg-error" : "bg-primary"}`}
                    style={{ width: `${Math.min(100, util)}%` }}
                  />
                </div>
              </div>
              <dl className="space-y-1.5 text-sm">
                <div className="flex justify-between"><dt className="text-muted">Current job</dt><dd className="font-medium text-ink">{m.current_operation ? m.current_operation.order_id : "idle"}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Next job</dt><dd className="font-medium text-ink">{m.next_operation ? m.next_operation.order_id : "-"}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Breakdowns (history)</dt><dd className="font-medium text-ink">{m.reliability.breakdown_count}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">MTBF</dt><dd className="font-medium text-ink">{m.reliability.mtbf_hours ? `${m.reliability.mtbf_hours}h` : "-"}</dd></div>
                <div className="flex justify-between"><dt className="text-muted">Maintenance windows</dt><dd className="font-medium text-ink">{m.maintenance_windows.length}</dd></div>
              </dl>
            </div>
          );
        })}
      </div>
    </div>
  );
}
