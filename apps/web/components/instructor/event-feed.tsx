"use client";

import { formatSimTime, type RoomEvent } from "@fogroom/shared";
import { useMemo, useState } from "react";
import { describeEvent, toneText, type EventCategory } from "@/lib/events";
import { cn } from "@/lib/utils";

const FILTERS: { key: EventCategory | "all"; label: string }[] = [
  { key: "all", label: "All" },
  { key: "scenario", label: "Scenario" },
  { key: "delivery", label: "Delivered" },
  { key: "delay", label: "Delayed" },
  { key: "drop", label: "Dropped" },
  { key: "conflict", label: "Conflicts" },
  { key: "channel", label: "Channels" },
  { key: "decision", label: "Decisions" },
  { key: "team", label: "Team" },
];

/** Live event feed with category filters. Pure/presentational - testable in isolation. */
export function EventFeed({ events, maxHeight = "28rem" }: { events: RoomEvent[]; maxHeight?: string }) {
  const [filter, setFilter] = useState<EventCategory | "all">("all");
  const rows = useMemo(
    () =>
      events
        .map((e) => ({ e, v: describeEvent(e) }))
        .filter((r): r is { e: RoomEvent; v: NonNullable<ReturnType<typeof describeEvent>> } => r.v !== null)
        .filter((r) => filter === "all" || r.v.category === filter),
    [events, filter],
  );

  return (
    <div>
      <div className="flex flex-wrap gap-1 border-b border-line px-3 py-2" role="toolbar" aria-label="Filter events">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            aria-pressed={filter === f.key}
            className={cn(
              "rounded px-2 py-1 text-[11px] font-medium",
              filter === f.key ? "bg-panel-3 text-fg" : "text-muted hover:text-fg",
            )}
          >
            {f.label}
          </button>
        ))}
      </div>
      <ol className="divide-y divide-line overflow-y-auto" style={{ maxHeight }} aria-live="polite" aria-label="Event feed">
        {rows.length === 0 && <li className="px-4 py-6 text-center text-xs text-muted">No events yet</li>}
        {rows.map(({ e, v }) => {
          const Icon = v.icon;
          return (
            <li key={`${e.seq}-${e.event_type}`} className="flex gap-3 px-3 py-2 animate-fr-in">
              <Icon className={cn("mt-0.5 size-3.5 shrink-0", toneText[v.tone])} aria-hidden />
              <div className="min-w-0 flex-1">
                <div className="flex items-baseline justify-between gap-2">
                  <p className="truncate text-xs text-fg">{v.title}</p>
                  <span className="shrink-0 font-mono text-[10px] tabular text-subtle">{formatSimTime(e.sim_time)}</span>
                </div>
                {v.detail && <p className="mt-0.5 line-clamp-2 text-[11px] text-muted">{v.detail}</p>}
              </div>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
