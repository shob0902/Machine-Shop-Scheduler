export default function StatCard({
  label, value, sub, tone = "default",
}: { label: string; value: string; sub?: string; tone?: "default" | "good" | "warn" | "bad" }) {
  const toneClasses: Record<string, string> = {
    default: "border-gray-200 bg-white",
    good: "border-green-200 bg-green-50",
    warn: "border-yellow-200 bg-yellow-50",
    bad: "border-red-200 bg-red-50",
  };
  return (
    <div className={`rounded-2xl border p-5 shadow-sm ${toneClasses[tone]}`}>
      <p className="text-sm font-medium uppercase tracking-wide text-gray-500">{label}</p>
      <p className="mt-2 text-3xl font-bold text-gray-900">{value}</p>
      {sub && <p className="mt-1 text-sm text-gray-500">{sub}</p>}
    </div>
  );
}
