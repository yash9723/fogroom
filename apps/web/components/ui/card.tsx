import * as React from "react";
import { cn } from "@/lib/utils";

export function Card({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("rounded-lg border border-line bg-panel", className)} {...props} />;
}

export function CardHeader({
  title,
  description,
  icon,
  actions,
  className,
}: {
  title: React.ReactNode;
  description?: React.ReactNode;
  icon?: React.ReactNode;
  actions?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex items-start justify-between gap-3 border-b border-line px-4 py-3", className)}>
      <div className="flex min-w-0 items-start gap-2.5">
        {icon && <span className="mt-0.5 text-accent [&_svg]:size-4">{icon}</span>}
        <div className="min-w-0">
          <h2 className="text-sm font-semibold tracking-wide text-fg">{title}</h2>
          {description && <p className="mt-0.5 text-xs text-muted">{description}</p>}
        </div>
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("p-4", className)} {...props} />;
}

export function StatCard({
  label,
  value,
  hint,
  tone,
  icon,
}: {
  label: string;
  value: React.ReactNode;
  hint?: React.ReactNode;
  tone?: "ok" | "warn" | "crit" | "off" | "accent";
  icon?: React.ReactNode;
}) {
  const toneClass = {
    ok: "text-ok",
    warn: "text-warn",
    crit: "text-crit",
    off: "text-muted",
    accent: "text-accent",
  }[tone ?? "accent"];
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between text-xs uppercase tracking-wider text-muted">
        <span>{label}</span>
        {icon && <span className="text-subtle [&_svg]:size-4">{icon}</span>}
      </div>
      <div className={cn("mt-2 font-mono text-2xl font-semibold tabular presentation-emphasis", toneClass)}>{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </Card>
  );
}
