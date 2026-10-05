"use client";

import { formatSimTime } from "@fogroom/shared";
import { CheckCircle2, CircleDot, FastForward, Flag, Vote, Zap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { TimelineItem } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Scenario timeline: fired vs upcoming events and decision points, with manual triggers. */
export function ScenarioTimeline({
  items,
  simTime,
  onFire,
  onOpenDecision,
  onSkipTo,
  disabled,
}: {
  items: TimelineItem[];
  simTime: number;
  onFire: (key: string) => void;
  onOpenDecision: (key: string) => void;
  onSkipTo: (t: number) => void;
  disabled?: boolean;
}) {
  return (
    <ol className="relative max-h-[30rem] space-y-1 overflow-y-auto px-3 py-3" aria-label="Scenario timeline">
      {items.map((item) => {
        const done = item.status !== "UPCOMING";
        const due = item.scheduled_sim_time;
        const Icon = item.kind === "DECISION" ? Vote : done ? CheckCircle2 : item.trigger_type === "MANUAL" ? Zap : Flag;
        return (
          <li
            key={`${item.kind}-${item.key}`}
            className={cn(
              "flex items-center gap-3 rounded-md border px-3 py-2",
              done ? "border-line bg-panel-2/40 opacity-75" : "border-line bg-panel-2",
            )}
          >
            <Icon className={cn("size-4 shrink-0", done ? "text-ok" : item.kind === "DECISION" ? "text-accent" : "text-muted")} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="font-mono text-[11px] tabular text-subtle">
                  {due !== null ? formatSimTime(due) : "manual"}
                </span>
                <span className="truncate text-xs font-medium">{item.title}</span>
              </div>
              <div className="mt-0.5 flex flex-wrap gap-1">
                <Badge tone={item.kind === "DECISION" ? "accent" : "neutral"}>{item.kind === "DECISION" ? "Decision" : item.event_type}</Badge>
                {item.has_variants && <Badge tone="violet">Variant</Badge>}
                {done && item.fired_sim_time !== null && (
                  <Badge tone="ok">
                    <CircleDot aria-hidden /> {item.status === "OPEN" ? "Open" : "Fired"} {formatSimTime(item.fired_sim_time)}
                  </Badge>
                )}
              </div>
            </div>
            {!done && (
              <div className="flex shrink-0 gap-1">
                {due !== null && due > simTime && (
                  <Button size="sm" variant="ghost" disabled={disabled} onClick={() => onSkipTo(due)} title="Fast-forward the clock to this moment">
                    <FastForward aria-hidden />
                  </Button>
                )}
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={disabled}
                  onClick={() => (item.kind === "DECISION" ? onOpenDecision(item.key) : onFire(item.key))}
                >
                  {item.kind === "DECISION" ? "Open now" : "Fire now"}
                </Button>
              </div>
            )}
          </li>
        );
      })}
    </ol>
  );
}
