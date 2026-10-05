"use client";

import { Activity, ShieldAlert, UserRound } from "lucide-react";
import { SimClock } from "@/components/sim-clock";
import { ConnectionIndicator } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { TraineeState } from "@/lib/types";
import { scoreTone } from "@/lib/utils";

export function TraineeTopbar({ state, fetchedAt }: { state: TraineeState; fetchedAt: number }) {
  const tone = scoreTone(state.communication_health);
  const toneClass = { ok: "text-ok", warn: "text-warn", crit: "text-crit", off: "text-muted" }[tone];
  return (
    <Card className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
      <div className="flex flex-wrap items-center gap-6">
        <SimClock
          simTime={state.room.sim_time}
          status={state.room.status}
          timeScale={state.room.time_scale}
          fetchedAt={fetchedAt}
          phase={state.room.phase?.name}
        />
        <div className="hidden h-10 w-px bg-line md:block" />
        <div>
          <div className="text-sm font-semibold">{state.room.scenario_name}</div>
          <div className="text-xs text-muted">Room {state.room.room_code}</div>
        </div>
      </div>
      <div className="flex flex-wrap items-center gap-4">
        <div className="flex items-center gap-2">
          <UserRound className="size-4 text-accent" aria-hidden />
          <div>
            <div className="font-mono text-sm font-semibold text-accent" data-testid="my-callsign">
              {state.participant.callsign}
            </div>
            <div className="text-[11px] text-muted">{state.participant.role_name}</div>
          </div>
        </div>
        <div className="flex items-center gap-2" title="Experimental communication health metric">
          <Activity className={`size-4 ${toneClass}`} aria-hidden />
          <div>
            <div className={`font-mono text-sm font-semibold tabular ${toneClass}`} data-testid="comm-health">
              {Math.round(state.communication_health)}%
            </div>
            <div className="text-[11px] text-muted">Comm health</div>
          </div>
        </div>
        {state.blackout && (
          <Badge tone="crit">
            <ShieldAlert aria-hidden /> Blackout
          </Badge>
        )}
        <ConnectionIndicator roomId={state.room.id} />
      </div>
    </Card>
  );
}
