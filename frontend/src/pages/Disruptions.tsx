import { useEffect, useState, type ReactNode } from "react";
import { disruptionApi } from "../services/api";
import type { DisruptionRecord, ScheduleResult } from "../types";
import { useStrategy } from "../hooks/useStrategy";
import { ErrorBanner } from "../components/LoadingError";
import StatusBadge from "../components/StatusBadge";
import { AlertIcon } from "../components/Icons";

type DisruptionType = "machine_breakdown" | "operator_absence" | "material_delay" | "rework" | "power_cut";

const TABS: { key: DisruptionType; label: string }[] = [
  { key: "machine_breakdown", label: "Machine Breakdown" },
  { key: "operator_absence", label: "Operator Absence" },
  { key: "material_delay", label: "Material Delay" },
  { key: "rework", label: "Rework" },
  { key: "power_cut", label: "Power Cut" },
];

export default function Disruptions() {
  const { strategy, bumpRefresh } = useStrategy();
  const [tab, setTab] = useState<DisruptionType>("machine_breakdown");
  const [history, setHistory] = useState<DisruptionRecord[]>([]);
  const [result, setResult] = useState<ScheduleResult | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<{ message: string; suggestion?: string } | null>(null);

  const [form, setForm] = useState<Record<string, string>>({
    machine_id: "GRIND-01", start_time: "2026-08-25T11:00", duration_minutes: "480", reason: "Bearing failure",
    operator_id: "OP-001", day_index: "1", shift: "1",
    order_id: "ORD-001", new_material_available_time: "2026-08-28T06:00",
    quantity: "50", operation_id: "",
    use_generator: "false",
  });

  const loadHistory = () => disruptionApi.list().then(setHistory).catch(() => {});
  useEffect(() => { loadHistory(); }, []);

  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const submit = async () => {
    setSubmitting(true);
    setError(null);
    setResult(null);
    try {
      let res: ScheduleResult;
      if (tab === "machine_breakdown") {
        res = await disruptionApi.breakdown({
          machine_id: form.machine_id, start_time: form.start_time, duration_minutes: Number(form.duration_minutes),
          reason: form.reason, strategy,
        });
      } else if (tab === "operator_absence") {
        res = await disruptionApi.operatorAbsence({
          operator_id: form.operator_id, day_index: Number(form.day_index), shift: Number(form.shift), strategy,
        });
      } else if (tab === "material_delay") {
        res = await disruptionApi.materialDelay({
          order_id: form.order_id, new_material_available_time: form.new_material_available_time, strategy,
        });
      } else if (tab === "rework") {
        res = await disruptionApi.rework({
          order_id: form.order_id, quantity: Number(form.quantity),
          operation_id: form.operation_id || null, strategy,
        });
      } else {
        res = await disruptionApi.powerCut({
          day_index: Number(form.day_index), shift: Number(form.shift),
          duration_minutes: Number(form.duration_minutes), use_generator: form.use_generator === "true", strategy,
        });
      }
      setResult(res);
      bumpRefresh();
      loadHistory();
    } catch (e: any) {
      setError({ message: e.message, suggestion: e.suggestion });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="neu-raised-sm px-5 py-4">
        <p className="text-sm text-muted">Stage a disruption, then replan. This is the heart of the system.</p>
      </div>

      <div className="neu-inset neu-scroll flex items-center gap-2 overflow-x-auto p-2">
        {TABS.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`shrink-0 rounded-xl px-4 py-2 text-xs font-semibold whitespace-nowrap transition-colors ${tab === t.key ? "neu-btn-primary" : "text-muted hover:text-ink"}`}
          >
            {t.label}
          </button>
        ))}
      </div>

      <div className="neu-raised p-6">
        {tab === "machine_breakdown" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Machine ID"><input className="neu-input" value={form.machine_id} onChange={(e) => set("machine_id", e.target.value)} /></Field>
            <Field label="Start Time"><input type="datetime-local" className="neu-input" value={form.start_time} onChange={(e) => set("start_time", e.target.value)} /></Field>
            <Field label="Duration (minutes)"><input type="number" className="neu-input" value={form.duration_minutes} onChange={(e) => set("duration_minutes", e.target.value)} /></Field>
            <Field label="Reason"><input className="neu-input" value={form.reason} onChange={(e) => set("reason", e.target.value)} /></Field>
          </div>
        )}
        {tab === "operator_absence" && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Operator ID"><input className="neu-input" value={form.operator_id} onChange={(e) => set("operator_id", e.target.value)} /></Field>
            <Field label="Day Index (0-13)"><input type="number" className="neu-input" value={form.day_index} onChange={(e) => set("day_index", e.target.value)} /></Field>
            <Field label="Shift (1 or 2)"><input type="number" className="neu-input" value={form.shift} onChange={(e) => set("shift", e.target.value)} /></Field>
          </div>
        )}
        {tab === "material_delay" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Order ID"><input className="neu-input" value={form.order_id} onChange={(e) => set("order_id", e.target.value)} /></Field>
            <Field label="New Material Available"><input type="datetime-local" className="neu-input" value={form.new_material_available_time} onChange={(e) => set("new_material_available_time", e.target.value)} /></Field>
          </div>
        )}
        {tab === "rework" && (
          <div className="grid gap-4 sm:grid-cols-3">
            <Field label="Order ID"><input className="neu-input" value={form.order_id} onChange={(e) => set("order_id", e.target.value)} /></Field>
            <Field label="Quantity"><input type="number" className="neu-input" value={form.quantity} onChange={(e) => set("quantity", e.target.value)} /></Field>
            <Field label="Operation ID (optional)"><input className="neu-input" value={form.operation_id} onChange={(e) => set("operation_id", e.target.value)} /></Field>
          </div>
        )}
        {tab === "power_cut" && (
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Day Index (0-13)"><input type="number" className="neu-input" value={form.day_index} onChange={(e) => set("day_index", e.target.value)} /></Field>
            <Field label="Shift (1 or 2)"><input type="number" className="neu-input" value={form.shift} onChange={(e) => set("shift", e.target.value)} /></Field>
            <Field label="Duration (minutes)"><input type="number" className="neu-input" value={form.duration_minutes} onChange={(e) => set("duration_minutes", e.target.value)} /></Field>
            <Field label="Option">
              <select className="neu-input" value={form.use_generator} onChange={(e) => set("use_generator", e.target.value)}>
                <option value="false">Lose the shift</option>
                <option value="true">Run diesel generator (3x cost)</option>
              </select>
            </Field>
          </div>
        )}

        <button
          onClick={submit}
          disabled={submitting}
          className="neu-btn-danger mt-5 flex items-center gap-2 px-6 py-3 text-sm font-bold"
        >
          {!submitting && <AlertIcon className="h-4 w-4" />}
          {submitting ? "Replanning..." : "REPLAN"}
        </button>
      </div>

      {error && <ErrorBanner message={error.message} suggestion={error.suggestion} />}

      {result && (
        <div className="space-y-4">
          {result.owner_action && (
            <div className="neu-raised border-l-4 border-primary p-6">
              <p className="mb-1 text-xs font-bold uppercase tracking-wide text-primary">Owner Action</p>
              <p className="text-lg font-semibold text-ink">{result.owner_action.headline}</p>
              {result.owner_action.reasons?.map((r, i) => (
                <p key={i} className="mt-1 text-sm text-muted">- {r}</p>
              ))}
              {result.owner_action.detail && <p className="mt-1 text-sm text-muted">{result.owner_action.detail}</p>}
            </div>
          )}

          <div className="neu-raised p-6">
            <p className="mb-3 text-base font-bold text-ink">Before / After Comparison</p>
            <div className="mb-4 grid grid-cols-2 gap-3 text-sm">
              <div className="neu-inset-sm p-3"><p className="text-muted">Frozen (already started)</p><p className="text-2xl font-bold text-ink">{result.frozen_operation_count}</p></div>
              <div className="neu-inset-sm p-3"><p className="text-muted">Re-optimized</p><p className="text-2xl font-bold text-ink">{result.reoptimized_operation_count}</p></div>
            </div>
            {result.comparison && (
              <>
                <div className="neu-scroll overflow-x-auto">
                  <table className="min-w-full text-sm">
                    <thead>
                      <tr>
                        {["Order", "Customer", "Old Completion", "New Completion", "Old Status", "New Status"].map((h) => (
                          <th key={h} className="px-3 py-2 text-left text-xs font-semibold uppercase tracking-wide text-muted">{h}</th>
                        ))}
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-dark-shadow/15">
                      {result.comparison.order_changes.filter((c) => c.moved).map((c) => (
                        <tr key={c.order_id}>
                          <td className="px-3 py-2 font-semibold text-ink">{c.order_id}</td>
                          <td className="px-3 py-2 text-ink">{c.customer}</td>
                          <td className="px-3 py-2 text-muted">{new Date(c.old_completion).toLocaleString()}</td>
                          <td className="px-3 py-2 text-muted">{new Date(c.new_completion).toLocaleString()}</td>
                          <td className="px-3 py-2"><StatusBadge status={c.old_status} /></td>
                          <td className="px-3 py-2"><StatusBadge status={c.new_status} /></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-3 text-sm sm:grid-cols-4">
                  <div className="neu-inset-sm p-3"><p className="text-muted">Moved operations</p><p className="text-xl font-bold text-ink">{result.comparison.moved_operation_count}</p></div>
                  <div className="neu-inset-sm p-3"><p className="text-muted">Newly late orders</p><p className="text-xl font-bold text-ink">{result.comparison.newly_late_orders.length}</p></div>
                  <div className="neu-inset-sm p-3"><p className="text-muted">New overtime ops</p><p className="text-xl font-bold text-ink">{result.comparison.new_overtime_operations.length}</p></div>
                  <div className="neu-inset-sm p-3"><p className="text-muted">Disruption cost</p><p className="text-xl font-bold text-error">Rs.{result.comparison.disruption_cost.toLocaleString()}</p></div>
                </div>
              </>
            )}
          </div>
        </div>
      )}

      <div className="neu-raised p-6">
        <p className="mb-3 text-base font-bold text-ink">Disruption History</p>
        {history.length === 0 ? (
          <p className="text-sm text-muted">No disruptions recorded yet.</p>
        ) : (
          <ul className="divide-y divide-dark-shadow/15 text-sm">
            {history.map((d) => (
              <li key={d.id} className="flex items-center justify-between py-2.5">
                <span className="font-medium text-ink">{d.disruption_type.replace(/_/g, " ")}</span>
                <span className="text-xs text-muted">{new Date(d.created_at).toLocaleString()}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-xs font-semibold uppercase tracking-wide text-muted">{label}</span>
      {children}
    </label>
  );
}
