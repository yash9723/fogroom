import { cva, type VariantProps } from "class-variance-authority";
import * as React from "react";
import { cn } from "@/lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded border px-1.5 py-0.5 text-[11px] font-medium uppercase tracking-wide [&_svg]:size-3",
  {
    variants: {
      tone: {
        neutral: "border-line-strong bg-panel-2 text-muted",
        accent: "border-accent/40 bg-accent-soft text-accent",
        ok: "border-ok/40 bg-ok-soft text-ok",
        warn: "border-warn/40 bg-warn-soft text-warn",
        crit: "border-crit/40 bg-crit-soft text-crit",
        off: "border-off/40 bg-off-soft text-off",
        info: "border-info/40 bg-[#14213a] text-info",
        violet: "border-violet/40 bg-[#211a3a] text-violet",
      },
    },
    defaultVariants: { tone: "neutral" },
  },
);

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement>, VariantProps<typeof badgeVariants> {}

export function Badge({ className, tone, ...props }: BadgeProps) {
  return <span className={cn(badgeVariants({ tone }), className)} {...props} />;
}
