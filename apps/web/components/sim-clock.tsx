"use client";

import { formatSimTime } from "@fogroom/shared";
import { Timer } from "lucide-react";
import { RoomStatusBadge } from "@/components/status/indicators";
import { useSimClock } from "@/hooks/use-sim-clock";
import { cn } from "@/lib/utils";

export function SimClock({
  simTime,
  status,
  timeScale,
  fetchedAt,
  phase,
  className,
}: {
  simTime: number;
  status: string;
  timeScale: number;
  fetchedAt: number;
  phase?: string | null;
  className?: string;
}) {
  const t = useSimClock(simTime, status, timeScale, fetchedAt);
  return (
    <div className={cn("flex items-center gap-3", className)}>
      <Timer className="size-5 text-accent" aria-hidden />
      <div>
        <div className="font-mono text-2xl font-semibold tabular tracking-wider presentation-emphasis" aria-label="Simulation time" data-testid="sim-clock">
          {formatSimTime(t)}
        </div>
        <div className="mt-0.5 flex items-center gap-2 text-[11px] text-muted">
          <RoomStatusBadge status={status} />
          {phase && <span>{phase}</span>}
          {timeScale !== 1 && <span className="font-mono">×{timeScale}</span>}
        </div>
      </div>
    </div>
  );
}
