import { useEffect, useState } from "react";
import { orderApi } from "../services/api";
import type { OrderSummary } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { Loading, ErrorBanner } from "../components/LoadingError";
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
      <h1 className="text-3xl font-bold text-gray-900">Orders</h1>
      <div className="flex gap-2">
        {["ALL", "ON_TRACK", "AT_RISK", "LATE"].map((f) => (
          <button
            key={f}
            onClick={() => setFilter(f)}
            className={`rounded-full px-3 py-1 text-sm font-medium ${filter === f ? "bg-blue-600 text-white" : "bg-white border border-gray-300 text-gray-700"}`}
          >
            {f.replace("_", " ")}
          </button>
        ))}
      </div>
      <div className="overflow-x-auto rounded-2xl border border-gray-200 bg-white">
        <table className="min-w-full divide-y divide-gray-200 text-sm">
          <thead className="bg-gray-50">
            <tr>
              {["Order", "Customer", "Tier", "Qty", "Due Date", "Promised", "Status", "Risk"].map((h) => (
                <th key={h} className="px-4 py-3 text-left font-semibold text-gray-600">{h}</th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-100">
            {filtered.map((o) => (
              <tr key={o.order_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 font-medium text-gray-900">{o.order_id}</td>
                <td className="px-4 py-3">{o.customer}</td>
                <td className="px-4 py-3">
                  <span className={`rounded-full px-2 py-0.5 text-xs font-semibold ${o.customer_tier === "Tier-1" ? "bg-purple-100 text-purple-800" : "bg-gray-100 text-gray-600"}`}>
                    {o.customer_tier}
                  </span>
                </td>
                <td className="px-4 py-3">{o.quantity.toLocaleString()}</td>
                <td className="px-4 py-3">{new Date(o.due_date).toLocaleString()}</td>
                <td className="px-4 py-3">{o.promised_completion ? new Date(o.promised_completion).toLocaleString() : "-"}</td>
                <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                <td className="px-4 py-3">{o.tardiness_hours > 0 ? `${o.tardiness_hours}h late` : "on time"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
