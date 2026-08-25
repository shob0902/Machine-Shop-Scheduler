// Minimal, single-color line icons (stroke = currentColor). Replaces emoji
// throughout the app, which read as informal/childish for a shop-floor
// production tool - see the Soft Neumorphism redesign brief, "Clean icons".
import type { SVGProps } from "react";

const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.75,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function DashboardIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <rect x="3.5" y="3.5" width="7.5" height="7.5" rx="1.5" />
      <rect x="13" y="3.5" width="7.5" height="4.5" rx="1.5" />
      <rect x="13" y="10.5" width="7.5" height="10" rx="1.5" />
      <rect x="3.5" y="13.5" width="7.5" height="7" rx="1.5" />
    </svg>
  );
}

export function ScheduleIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <rect x="3.5" y="4.5" width="17" height="16" rx="2" />
      <path d="M3.5 9.5h17" />
      <path d="M8 2.5v4M16 2.5v4" />
      <path d="M7.5 13.5h3M7.5 17h3M13.5 13.5h3M13.5 17h3" />
    </svg>
  );
}

export function OrdersIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <rect x="5" y="4" width="14" height="17" rx="2" />
      <path d="M9 2.5h6a1 1 0 0 1 1 1V5H8V3.5a1 1 0 0 1 1-1Z" />
      <path d="M8.5 11h7M8.5 14.5h7M8.5 18h4.5" />
    </svg>
  );
}

export function MachinesIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="3.25" />
      <path d="M12 3.5v2.4M12 18.1v2.4M20.5 12h-2.4M5.9 12H3.5M17.6 6.4l-1.7 1.7M8.1 15.9l-1.7 1.7M17.6 17.6l-1.7-1.7M8.1 8.1 6.4 6.4" />
    </svg>
  );
}

export function DisruptionsIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3.5 21 19.5H3L12 3.5Z" />
      <path d="M12 10v4" />
      <circle cx="12" cy="16.6" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function StrategyIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3v18M7 6.5h10" />
      <path d="M4.5 6.5 2 12a2.5 2.5 0 0 0 5 0L4.5 6.5ZM19.5 6.5 17 12a2.5 2.5 0 0 0 5 0l-2.5-5.5Z" />
      <path d="M8.5 20.5h7" />
    </svg>
  );
}

export function CostIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <circle cx="12" cy="12" r="9" />
      <path d="M9.25 8.5h4.75a2 2 0 1 1 0 4H9.25M9.25 8.5 12 15.5M9.25 12.5h4" />
    </svg>
  );
}

export function AlertIcon(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M12 3.5 21 19.5H3L12 3.5Z" />
      <path d="M12 10v4" />
      <circle cx="12" cy="16.6" r="0.9" fill="currentColor" stroke="none" />
    </svg>
  );
}

export function LogoMark(props: SVGProps<SVGSVGElement>) {
  return (
    <svg {...base} {...props}>
      <path d="M4 7 12 3l8 4v10l-8 4-8-4V7Z" />
      <path d="M4 7l8 4 8-4M12 11v10" />
    </svg>
  );
}
