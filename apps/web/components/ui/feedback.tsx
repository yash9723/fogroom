import { AlertTriangle, Inbox } from "lucide-react";
import * as React from "react";
import { cn } from "@/lib/utils";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("animate-pulse rounded-md bg-panel-3/70", className)} aria-hidden />;
}

export function LoadingBlock({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div className={cn("space-y-2", className)} role="status" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-10 w-full" />
      ))}
    </div>
  );
}

export function EmptyState({
  title,
  description,
  icon,
  action,
  className,
}: {
  title: string;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center justify-center px-6 py-10 text-center", className)}>
      <div className="mb-3 text-subtle [&_svg]:size-7">{icon ?? <Inbox />}</div>
      <p className="text-sm font-medium text-fg">{title}</p>
      {description && <p className="mt-1 max-w-sm text-xs text-muted">{description}</p>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, action }: { message: string; action?: React.ReactNode }) {
  return (
    <div role="alert" className="flex items-start gap-3 rounded-lg border border-crit/40 bg-crit-soft p-4 text-sm text-crit">
      <AlertTriangle className="mt-0.5 size-4 shrink-0" />
      <div className="flex-1">
        <p>{message}</p>
        {action && <div className="mt-3">{action}</div>}
      </div>
    </div>
  );
}

export function PageHeader({
  title,
  description,
  actions,
  eyebrow,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  actions?: React.ReactNode;
  eyebrow?: React.ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        {eyebrow && <div className="mb-1 text-xs font-medium uppercase tracking-widest text-accent">{eyebrow}</div>}
        <h1 className="text-xl font-semibold tracking-tight text-fg">{title}</h1>
        {description && <p className="mt-1 max-w-3xl text-sm text-muted">{description}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

/** Horizontal 0-100 meter with numeric label (never colour-only). */
export function Meter({
  value,
  label,
  tone = "accent",
  invert = false,
}: {
  value: number | null | undefined;
  label: string;
  tone?: "ok" | "warn" | "crit" | "off" | "accent";
  invert?: boolean;
}) {
  const v = Math.max(0, Math.min(100, value ?? 0));
  const bar = { ok: "bg-ok", warn: "bg-warn", crit: "bg-crit", off: "bg-off", accent: "bg-accent" }[tone];
  return (
    <div>
      <div className="mb-1 flex items-center justify-between text-xs">
        <span className="text-muted">{label}</span>
        <span className="font-mono tabular text-fg">{value === null || value === undefined ? "-" : Math.round(v)}</span>
      </div>
      <div
        className="h-1.5 overflow-hidden rounded-full bg-panel-3"
        role="meter"
        aria-label={label}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(v)}
        data-invert={invert || undefined}
      >
        <div className={cn("h-full rounded-full transition-all", bar)} style={{ width: `${v}%` }} />
      </div>
    </div>
  );
}
