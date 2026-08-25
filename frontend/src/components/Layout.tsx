import React from "react";
import { NavLink, useLocation } from "react-router-dom";
import { useStrategy } from "../hooks/useStrategy";
import type { Strategy } from "../types";
import {
  DashboardIcon, ScheduleIcon, OrdersIcon, MachinesIcon, DisruptionsIcon, StrategyIcon, CostIcon, LogoMark,
} from "./Icons";

const NAV_ITEMS = [
  { to: "/", label: "Dashboard", Icon: DashboardIcon },
  { to: "/schedule", label: "Schedule", Icon: ScheduleIcon },
  { to: "/orders", label: "Orders", Icon: OrdersIcon },
  { to: "/machines", label: "Machines", Icon: MachinesIcon },
  { to: "/disruptions", label: "Disruptions", Icon: DisruptionsIcon },
  { to: "/strategies", label: "Strategy Comparison", Icon: StrategyIcon },
  { to: "/costs", label: "Cost Analysis", Icon: CostIcon },
];

const STRATEGY_LABELS: Record<Strategy, string> = {
  cheapest: "Cheapest",
  most_on_time: "Most On-Time",
  most_robust: "Most Robust",
};

export default function Layout({ children }: { children: React.ReactNode }) {
  const { strategy, setStrategy, bumpRefresh } = useStrategy();
  const location = useLocation();
  const currentTitle = NAV_ITEMS.find((n) =>
    n.to === "/" ? location.pathname === "/" : location.pathname.startsWith(n.to)
  )?.label ?? "Dashboard";

  return (
    <div className="app-shell flex min-h-screen bg-bg text-ink">
      {/* SIDEBAR */}
      <aside className="hidden w-72 shrink-0 flex-col gap-6 p-5 md:flex">
        <div className="neu-raised-sm flex items-center gap-3 px-4 py-4">
          <div className="neu-inset-sm flex h-11 w-11 items-center justify-center rounded-2xl text-primary">
            <LogoMark className="h-6 w-6" />
          </div>
          <div>
            <p className="text-sm font-extrabold uppercase tracking-wide text-ink">Machine Shop</p>
            <p className="text-xs font-medium text-muted">Scheduler</p>
          </div>
        </div>

        <nav className="neu-raised-sm flex-1 space-y-1 p-3">
          {NAV_ITEMS.map(({ to, label, Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === "/"}
              className={({ isActive }) => `neu-nav-item ${isActive ? "neu-nav-item-active" : ""}`}
            >
              <Icon className="h-5 w-5 shrink-0" />
              <span className="text-sm">{label}</span>
            </NavLink>
          ))}
        </nav>

        <div className="neu-raised-sm space-y-3 p-4">
          <label className="block text-xs font-semibold uppercase tracking-wide text-muted">
            Active Strategy
          </label>
          <select
            className="neu-input text-sm font-medium"
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
          <div className="flex items-center gap-2 pt-1 text-xs font-semibold text-muted">
            <span className="h-2 w-2 rounded-full bg-success" />
            Shop Operational
          </div>
        </div>
      </aside>

      {/* MAIN COLUMN */}
      <div className="flex min-h-screen min-w-0 flex-1 flex-col">
        {/* MOBILE TOPBAR */}
        <header className="flex flex-col gap-3 px-4 pt-4 md:hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="neu-inset-sm flex h-9 w-9 items-center justify-center rounded-xl text-primary">
                <LogoMark className="h-5 w-5" />
              </div>
              <p className="text-sm font-bold text-ink">Machine Shop Scheduler</p>
            </div>
            <select
              className="neu-input w-auto text-xs"
              value={strategy}
              onChange={(e) => setStrategy(e.target.value as Strategy)}
            >
              {Object.entries(STRATEGY_LABELS).map(([value, label]) => (
                <option key={value} value={value}>{label}</option>
              ))}
            </select>
          </div>

          {/* Horizontally-scrolling nav strip - the sidebar is hidden below md,
              so this is the only way to switch pages on phone/tablet. */}
          <nav className="neu-inset neu-scroll flex gap-1 overflow-x-auto p-1.5">
            {NAV_ITEMS.map(({ to, label, Icon }) => (
              <NavLink
                key={to}
                to={to}
                end={to === "/"}
                className={({ isActive }) =>
                  `flex shrink-0 items-center gap-1.5 rounded-xl px-3 py-2 text-xs font-semibold whitespace-nowrap ${
                    isActive ? "neu-raised-sm text-primary-dark" : "text-muted"
                  }`
                }
              >
                <Icon className="h-4 w-4 shrink-0" />
                {label}
              </NavLink>
            ))}
          </nav>
        </header>

        {/* DESKTOP TOPBAR */}
        <header className="hidden items-center justify-between px-8 pt-6 md:flex">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-muted">Sridhar Precision Works</p>
            <h1 className="text-2xl font-bold text-ink">{currentTitle}</h1>
          </div>
          <div className="neu-raised-sm flex items-center gap-2 px-4 py-2 text-sm font-medium text-muted">
            <span className="h-2 w-2 rounded-full bg-success" />
            Live data &middot; 14 machines &middot; 2 shifts
          </div>
        </header>

        <main className="min-w-0 flex-1 overflow-x-hidden overflow-y-auto p-5 md:p-8">{children}</main>
      </div>
    </div>
  );
}
