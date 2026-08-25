export default function StatCard({
  label, value, sub, tone = "default",
}: { label: string; value: string; sub?: string; tone?: "default" | "good" | "warn" | "bad" }) {
  const dotClasses: Record<string, string> = {
    default: "bg-primary",
    good: "bg-success",
    warn: "bg-warning",
    bad: "bg-error",
  };
  return (
    <div className="neu-raised min-w-0 p-5">
      <div className="flex items-center justify-between gap-2">
        <p className="text-xs font-semibold uppercase tracking-wide text-muted">{label}</p>
        <span className={`h-2 w-2 shrink-0 rounded-full ${dotClasses[tone]}`} />
      </div>
      <p className="mt-2 text-2xl leading-tight font-bold break-words text-ink sm:text-3xl">{value}</p>
      {sub && <p className="mt-1 text-sm text-muted">{sub}</p>}
    </div>
  );
}
