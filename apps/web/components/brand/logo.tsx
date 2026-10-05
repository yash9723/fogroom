import { cn } from "@/lib/utils";

/** FOGROOM mark: concentric signal arcs partially obscured by fog bands. */
export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden>
      <rect x="1" y="1" width="30" height="30" rx="7" fill="#0f1a22" stroke="#2e3a4a" />
      <circle cx="16" cy="16" r="2.4" fill="#4fc1d6" />
      <path d="M10.5 16a5.5 5.5 0 0 1 11 0" fill="none" stroke="#4fc1d6" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M6.5 16a9.5 9.5 0 0 1 19 0" fill="none" stroke="#4fc1d6" strokeOpacity="0.55" strokeWidth="1.6" strokeLinecap="round" />
      <path d="M5 20.5h22M8 24h16" stroke="#8b98a9" strokeOpacity="0.55" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export function Logo({ className, subtitle = false }: { className?: string; subtitle?: boolean }) {
  return (
    <div className={cn("flex items-center gap-2.5", className)}>
      <LogoMark />
      <div className="leading-tight">
        <div className="font-mono text-sm font-semibold tracking-[0.22em] text-fg">FOGROOM</div>
        {subtitle && <div className="text-[10px] uppercase tracking-wider text-muted">Decision training</div>}
      </div>
    </div>
  );
}
