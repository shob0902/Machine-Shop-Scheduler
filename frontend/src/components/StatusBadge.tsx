import type { OrderStatus } from "../types";

const CONFIG: Record<string, { label: string; classes: string; dot: string }> = {
  ON_TRACK: { label: "ON TRACK", classes: "bg-success/15 text-success", dot: "bg-success" },
  AT_RISK: { label: "AT RISK", classes: "bg-warning/15 text-[#8a5c14]", dot: "bg-warning" },
  LATE: { label: "LATE", classes: "bg-error/15 text-error", dot: "bg-error" },
  UNSCHEDULED: { label: "UNSCHEDULED", classes: "bg-dark-shadow/40 text-muted", dot: "bg-muted" },
  DOWN: { label: "MACHINE DOWN", classes: "bg-ink text-white", dot: "bg-white" },
  OPERATIONAL: { label: "OPERATIONAL", classes: "bg-success/15 text-success", dot: "bg-success" },
};

export default function StatusBadge({ status }: { status: OrderStatus | string }) {
  const cfg = CONFIG[status] || CONFIG.UNSCHEDULED;
  return (
    <span className={`neu-chip ${cfg.classes}`}>
      <span className={`h-2 w-2 rounded-full ${cfg.dot}`} />
      {cfg.label}
    </span>
  );
}
