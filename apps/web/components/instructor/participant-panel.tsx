"use client";

import { AlertTriangle } from "lucide-react";
import { PresenceBadge } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Meter } from "@/components/ui/feedback";
import type { InstructorParticipant } from "@/lib/types";
import { scoreTone, uncertaintyTone } from "@/lib/utils";

export function ParticipantPanel({ participants, blackoutIds }: { participants: InstructorParticipant[]; blackoutIds: Set<string> }) {
  return (
    <ul className="divide-y divide-line">
      {participants.map((p) => {
        const m = p.metrics;
        return (
          <li key={p.id} className="px-4 py-3" data-testid={`participant-${p.callsign}`}>
            <div className="flex items-center justify-between gap-2">
              <div>
                <span className="font-mono text-sm font-semibold text-accent">{p.callsign}</span>
                <span className="ml-2 text-xs text-muted">{p.role_name}</span>
              </div>
              <div className="flex gap-1">
                {blackoutIds.has(p.id) && <Badge tone="crit">Blackout</Badge>}
                <PresenceBadge status={p.connection_status} />
              </div>
            </div>
            <div className="mt-2 flex flex-wrap gap-1 text-[11px]">
              <Badge tone="ok">{p.deliveries.received} received</Badge>
              <Badge tone="warn">{p.deliveries.in_flight} in flight</Badge>
              <Badge tone="crit">{p.deliveries.dropped} dropped</Badge>
              {p.deliveries.altered > 0 && <Badge tone="violet">{p.deliveries.altered} altered</Badge>}
            </div>
            {m && (
              <div className="mt-3 grid grid-cols-2 gap-x-4 gap-y-2">
                <Meter label="Uncertainty index" value={m.uncertainty_index} tone={uncertaintyTone(m.uncertainty_index)} invert />
                <Meter label="Completeness" value={m.information_completeness} tone={scoreTone(m.information_completeness)} />
                <Meter label="Comm health" value={m.communication_health} tone={scoreTone(m.communication_health)} />
                <Meter label="Reliability" value={m.information_reliability} tone={scoreTone(m.information_reliability)} />
                {m.known_contradictions > 0 && (
                  <p className="col-span-2 flex items-center gap-1 text-[11px] text-violet">
                    <AlertTriangle className="size-3" aria-hidden /> Holding {m.known_contradictions} contradictory report set(s)
                  </p>
                )}
              </div>
            )}
          </li>
        );
      })}
    </ul>
  );
}
