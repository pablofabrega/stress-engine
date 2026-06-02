"use client";

import { AlertTriangle, Loader2, Inbox } from "lucide-react";
import type { ReactNode } from "react";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-steel">
      <Loader2 className="animate-spin" size={16} />
      {label ?? "Loading…"}
    </div>
  );
}

/** Shimmer placeholders shown while a request is in flight. */
export function LoadingSkeleton({ rows = 3 }: { rows?: number }) {
  return (
    <div className="space-y-4" aria-busy="true" aria-live="polite">
      <div className="grid gap-4 md:grid-cols-3">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="h-28 animate-pulse rounded-3xl border border-ink/10 bg-panel/70" />
        ))}
      </div>
      {Array.from({ length: rows }).map((_, i) => (
        <div key={i} className="h-16 animate-pulse rounded-2xl border border-ink/10 bg-panel/60" />
      ))}
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  return (
    <div className="flex flex-col items-start gap-3 rounded-3xl border border-[#9c3b2e]/30 bg-[#9c3b2e]/5 p-6">
      <div className="flex items-center gap-2 text-[#9c3b2e]">
        <AlertTriangle size={18} />
        <p className="font-medium">Something went wrong</p>
      </div>
      <p className="text-sm text-steel">{message}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="rounded-full bg-ink px-4 py-2 text-sm text-white transition-colors hover:bg-steel"
        >
          Retry
        </button>
      )}
    </div>
  );
}

export function EmptyState({ title, hint, action }: { title: string; hint?: string; action?: ReactNode }) {
  return (
    <div className="flex flex-col items-center gap-3 rounded-3xl border border-dashed border-ink/20 bg-white/40 p-10 text-center">
      <Inbox className="text-steel" size={24} />
      <p className="font-serif text-xl text-ink">{title}</p>
      {hint && <p className="max-w-md text-sm text-steel">{hint}</p>}
      {action}
    </div>
  );
}
