import type { OrderStatus } from "../types";

const CONFIG: Record<string, { label: string; classes: string; dot: string }> = {
  ON_TRACK: { label: "ON TRACK", classes: "bg-green-100 text-green-800 border-green-300", dot: "bg-green-500" },
  AT_RISK: { label: "AT RISK", classes: "bg-yellow-100 text-yellow-800 border-yellow-300", dot: "bg-yellow-500" },
  LATE: { label: "LATE", classes: "bg-red-100 text-red-800 border-red-300", dot: "bg-red-500" },
  UNSCHEDULED: { label: "UNSCHEDULED", classes: "bg-gray-100 text-gray-700 border-gray-300", dot: "bg-gray-400" },
  DOWN: { label: "MACHINE DOWN", classes: "bg-black text-white border-black", dot: "bg-white" },
  OPERATIONAL: { label: "OPERATIONAL", classes: "bg-green-100 text-green-800 border-green-300", dot: "bg-green-500" },
};

export default function StatusBadge({ status }: { status: OrderStatus | string }) {
  const cfg = CONFIG[status] || CONFIG.UNSCHEDULED;
  return (
    <span
      className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-sm font-semibold ${cfg.classes}`}
    >
      <span className={`h-2.5 w-2.5 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
