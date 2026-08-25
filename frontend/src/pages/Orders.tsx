import { useEffect, useState } from "react";
import { orderApi } from "../services/api";
import type { OrderSummary } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { Loading, ErrorBanner, EmptyState } from "../components/LoadingError";
import StatusBadge from "../components/StatusBadge";

export default function Orders() {
  const { strategy, refreshKey } = useStrategy();
  const [orders, setOrders] = useState<OrderSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);
  const [filter, setFilter] = useState<string>("ALL");

  useEffect(() => {
    setLoading(true);
    orderApi.list(strategy)
      .then(setOrders)
      .catch((e) => setError({ message: e.message, suggestion: e.suggestion }))
      .finally(() => setLoading(false));
  }, [strategy, refreshKey]);

  if (loading) return <Loading label="Loading orders..." />;
  if (error) return <ErrorBanner message={error.message} suggestion={error.suggestion} />;

  const filtered = filter === "ALL" ? orders : orders.filter((o) => o.status === filter);

  return (
    <div className="space-y-4">
      <div className="neu-inset flex flex-wrap gap-2 p-2">
        {["ALL", "ON_TRACK", "AT_RISK", "LATE"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-xl px-3 py-1.5 text-xs font-semibold transition-colors ${filter === f ? "neu-btn-primary" : "text-muted hover:text-ink"}`}
          >
            {f.replace("_", " ")}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <EmptyState title="No orders match this filter" message="Try a different status filter above." />
      ) : (
        <div className="neu-raised neu-scroll overflow-x-auto p-2">
          <table className="min-w-full text-sm">
            <thead>
              <tr>
                {["Order", "Customer", "Tier", "Qty", "Due Date", "Promised", "Status", "Risk"].map((h) => (
                  <th key={h} className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wide text-muted">{h}</th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-dark-shadow/15">
              {filtered.map((o) => (
                <tr key={o.order_id} className="transition-colors hover:bg-dark-shadow/10">
                  <td className="px-4 py-3 font-semibold text-ink">{o.order_id}</td>
                  <td className="px-4 py-3 text-ink">{o.customer}</td>
                  <td className="px-4 py-3">
                    <span className={`neu-chip ${o.customer_tier === "Tier-1" ? "bg-accent/15 text-accent" : "bg-dark-shadow/40 text-muted"}`}>
                      {o.customer_tier}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-ink">{o.quantity.toLocaleString()}</td>
                  <td className="px-4 py-3 text-muted">{new Date(o.due_date).toLocaleString()}</td>
                  <td className="px-4 py-3 text-muted">{o.promised_completion ? new Date(o.promised_completion).toLocaleString() : "-"}</td>
                  <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                  <td className="px-4 py-3 text-ink">{o.tardiness_hours > 0 ? `${o.tardiness_hours}h late` : "on time"}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
