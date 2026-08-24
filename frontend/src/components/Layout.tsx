import React from "react";
import { NavLink } from "react-router-dom";
import { useStrategy } from "../hooks/useStrategy";
import type { Strategy } from "../types";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", icon: "\u{1F4CA}" },
  { to: "/schedule", label: "Schedule", icon: "\u{1F4C5}" },
  { to: "/orders", label: "Orders", icon: "\u{1F4E6}" },
  { to: "/machines", label: "Machines", icon: "\u{1F3ED}" },
  { to: "/disruptions", label: "Disruptions", icon: "\u{26A0}\u{FE0F}" },
  { to: "/strategies", label: "Strategy Comparison", icon: "\u{2696}\u{FE0F}" },
  { to: "/costs", label: "Cost Analysis", icon: "\u{1F4B0}" },
];

const STRATEGY_LABELS: Record<Strategy, string> = {
  cheapest: "Cheapest",
  most_on_time: "Most On-Time",
  most_robust: "Most Robust",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  const { strategy, setStrategy, bumpRefresh } = useStrategy();

  return (
    <div className="app-shell flex min-h-screen bg-gray-100">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-gray-200 bg-white md:flex">
        <div className="border-b border-gray-200 px-5 py-6">
          <p className="text-xl font-bold text-gray-900">Sridhar Precision Works</p>
          <p className="text-sm text-gray-500">Machine Shop Scheduler</p>
        </div>
        <nav className="flex-1 space-y-1 px-3 py-4">
          {NAV_ITEMS.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-3 rounded-lg px-4 py-3 text-lg font-medium transition-colors ${
                  isActive ? "bg-blue-600 text-white" : "text-gray-700 hover:bg-gray-100"
                }`
              }
            >
              <span className="text-xl">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-gray-200 p-4">
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-gray-500">
            Active Strategy
          </label>
          <select
            className="w-full rounded-lg border border-gray-300 bg-white px-3 py-2 text-base font-medium"
            value={strategy}
            onChange={(e) => {
              setStrategy(e.target.value as Strategy);
              bumpRefresh();
            }}
          >
            {Object.entries(STRATEGY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </div>
      </aside>

      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        <header className="flex items-center justify-between border-b border-gray-200 bg-white px-6 py-4 md:hidden">
          <p className="text-lg font-bold">Sridhar Precision Works</p>
          <select
            className="rounded-lg border border-gray-300 px-2 py-1 text-sm"
            value={strategy}
            onChange={(e) => setStrategy(e.target.value as Strategy)}
          >
            {Object.entries(STRATEGY_LABELS).map(([value, label]) => (
              <option key={value} value={value}>{label}</option>
            ))}
          </select>
        </header>
        <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-4 md:p-8">{children}</main>
      </div>
    </div>
  );
}
