import { useMemo, useState } from "react";
import type { Machine, ScheduledOperation } from "../types";

const PIXELS_PER_HOUR = 26;
const DAY_SPAN_HOURS = 18; // 06:00 -> 24:00 (16 regular + 2 overtime hours modelled)
const DAY_WIDTH = DAY_SPAN_HOURS * PIXELS_PER_HOUR;
const ROW_HEIGHT = 56;

const FAMILY_COLORS: Record<string, string> = {
  Shaft: "bg-sky-500", Flange: "bg-emerald-500", Housing: "bg-amber-500",
  Bracket: "bg-violet-500", Gear: "bg-rose-500", Pin: "bg-teal-500",
};

function hoursIntoWindow(iso: string): number {
  const d = new Date(iso);
  const h = d.getHours() + d.getMinutes() / 60 - 6;
  return Math.max(0, Math.min(DAY_SPAN_HOURS, h));
}

function xFor(op: ScheduledOperation): number {
  return op.day_index * DAY_WIDTH + hoursIntoWindow(op.start_time) * PIXELS_PER_HOUR;
}

function widthFor(op: ScheduledOperation): number {
  const hrs = Math.max(0.25, (new Date(op.end_time).getTime() - new Date(op.start_time).getTime()) / 3_600_000);
  return hrs * PIXELS_PER_HOUR;
}

export default function Gantt({ machines, operations, horizonDays = 14 }: {
  machines: Machine[]; operations: ScheduledOperation[]; horizonDays?: number;
}) {
  const [selected, setSelected] = useState<ScheduledOperation | null>(null);
  const byMachine = useMemo(() => {
    const map = new Map<string, ScheduledOperation[]>();
    for (const m of machines) map.set(m.machine_id, []);
    for (const op of operations) {
      if (!map.has(op.machine_id)) map.set(op.machine_id, []);
      map.get(op.machine_id)!.push(op);
    }
    return map;
  }, [machines, operations]);

  const totalWidth = horizonDays * DAY_WIDTH;

  return (
    <div className="rounded-2xl border border-gray-200 bg-white p-4">
      <div className="mb-3 flex flex-wrap items-center gap-4 text-sm">
        <span className="font-semibold text-gray-700">Part family:</span>
        {Object.entries(FAMILY_COLORS).map(([fam, cls]) => (
          <span key={fam} className="flex items-center gap-1">
            <span className={`h-3 w-3 rounded ${cls}`} /> {fam}
          </span>
        ))}
        <span className="flex items-center gap-1"><span className="h-3 w-3 rounded bg-gray-400" /> Maintenance</span>
      </div>

      <div className="overflow-x-auto">
        <div style={{ width: totalWidth + 176 }}>
          {/* Day header row */}
          <div className="flex" style={{ marginLeft: 176 }}>
            {Array.from({ length: horizonDays }).map((_, d) => (
              <div key={d} style={{ width: DAY_WIDTH }} className="border-r border-gray-100 py-1 text-center text-xs font-semibold text-gray-500">
                Day {d + 1}
              </div>
            ))}
          </div>

          {machines.map((m) => {
            const ops = (byMachine.get(m.machine_id) || []).sort((a, b) => a.start_bucket - b.start_bucket);
            return (
              <div key={m.machine_id} className="flex border-t border-gray-100" style={{ height: ROW_HEIGHT }}>
                <div className="flex w-44 shrink-0 flex-col justify-center pr-2">
                  <p className="truncate text-sm font-semibold text-gray-800">{m.machine_name}</p>
                  <p className="text-xs text-gray-400">{m.machine_id}</p>
                </div>
                <div className="relative" style={{ width: totalWidth, height: ROW_HEIGHT }}>
                  {m.maintenance_windows.map((w: any, i: number) => (
                    <div
                      key={`maint-${i}`}
                      className="absolute top-2 rounded bg-gray-300"
                      style={{
                        left: w.day_index * DAY_WIDTH + (w.start_hour - 6) * PIXELS_PER_HOUR,
                        width: Math.max(4, (w.end_hour - w.start_hour) * PIXELS_PER_HOUR),
                        height: ROW_HEIGHT - 16,
                      }}
                      title={`Maintenance: ${w.description}`}
                    />
                  ))}
                  {ops.map((op) => (
                    <button
                      key={op.operation_id}
                      onClick={() => setSelected(op)}
                      className={`absolute top-2 overflow-hidden rounded text-left text-[11px] font-medium text-white shadow ${FAMILY_COLORS[op.part_family] || "bg-gray-500"} ${op.is_overtime ? "ring-2 ring-red-400" : ""}`}
                      style={{ left: xFor(op), width: Math.max(6, widthFor(op) - 2), height: ROW_HEIGHT - 16 }}
                      title={`${op.order_id} - ${op.operation_type} (${op.quantity}pc)`}
                    >
                      <span className="block truncate px-1 pt-1">{op.order_id}</span>
                    </button>
                  ))}
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4" onClick={() => setSelected(null)}>
          <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <div className="mb-3 flex items-start justify-between">
              <h3 className="text-xl font-bold">{selected.order_id}</h3>
              <button onClick={() => setSelected(null)} className="text-2xl leading-none text-gray-400 hover:text-gray-700">&times;</button>
            </div>
            <dl className="space-y-1 text-sm">
              <Row label="Operation" value={`${selected.operation_type} (seq ${selected.sequence})`} />
              <Row label="Machine" value={selected.machine_id} />
              <Row label="Operator" value={selected.operator_id} />
              <Row label="Quantity" value={String(selected.quantity)} />
              <Row label="Part family" value={selected.part_family} />
              <Row label="Start" value={new Date(selected.start_time).toLocaleString()} />
              <Row label="End" value={new Date(selected.end_time).toLocaleString()} />
              <Row label="Shift" value={`Shift ${selected.shift}${selected.is_overtime ? " (Overtime)" : ""}`} />
              <Row label="Changeover before" value={`${selected.changeover_minutes_before} min${selected.previous_family_on_machine ? ` (from ${selected.previous_family_on_machine})` : ""}`} />
              <Row label="Status" value={selected.status} />
            </dl>
          </div>
        </div>
      )}
    </div>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between border-b border-gray-100 py-1.5">
      <dt className="text-gray-500">{label}</dt>
      <dd className="font-medium text-gray-800">{value}</dd>
    </div>
  );
}
