import type { ReactNode } from "react";
import { AlertIcon } from "./Icons";

export function Loading({ label = "Loading..." }: { label?: string }) {
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-4 md:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="neu-skeleton h-24" />
        ))}
      </div>
      <div className="neu-skeleton h-64" />
      <div className="flex flex-col items-center justify-center py-6 text-muted">
        <div className="mb-3 h-8 w-8 animate-spin rounded-full border-4 border-dark-shadow border-t-primary" />
        <p className="text-sm font-medium">{label}</p>
      </div>
    </div>
  );
}

export function ErrorBanner({ message, suggestion }: { message: string; suggestion?: string }) {
  return (
    <div className="neu-raised border-l-4 border-error p-6">
      <div className="flex items-start gap-3">
        <AlertIcon className="h-6 w-6 shrink-0 text-error" />
        <div>
          <p className="text-lg font-bold text-error">Something went wrong</p>
          <p className="mt-1 text-ink">{message}</p>
          {suggestion && <p className="mt-2 text-sm text-muted">Suggestion: {suggestion}</p>}
        </div>
      </div>
    </div>
  );
}

export function EmptyState({ title, message, action }: { title: string; message: string; action?: ReactNode }) {
  return (
    <div className="neu-raised flex flex-col items-center justify-center gap-2 p-12 text-center">
      <p className="text-lg font-bold text-ink">{title}</p>
      <p className="max-w-sm text-sm text-muted">{message}</p>
      {action && <div className="mt-3">{action}</div>}
    </div>
  );
}
