"use client";

import { formatSimTime, type RoomEvent } from "@fogroom/shared";
import { useState } from "react";
import { Select } from "@/components/ui/form";
import { LoadingBlock } from "@/components/ui/feedback";
import { useTimeline } from "@/features/aar";
import { describeEvent, toneText } from "@/lib/events";
import { cn } from "@/lib/utils";

const TYPE_FILTERS: { value: string; label: string; types?: string[] }[] = [
  { value: "", label: "All event types" },
  { value: "scenario", label: "Scenario events", types: ["scenario", "phase"] },
  { value: "messages", label: "Messages created", types: ["message.created"] },
  { value: "delivery", label: "Deliveries", types: ["delivery"] },
  { value: "delayed", label: "Delays / holds", types: ["message.delayed", "message.held", "message.released"] },
  { value: "dropped", label: "Drops / failures", types: ["message.dropped", "message.failed"] },
  { value: "conflict", label: "Conflicts", types: ["conflict"] },
  { value: "channel", label: "Channel changes", types: ["channel"] },
  { value: "disruption", label: "Disruptions", types: ["disruption"] },
  { value: "decision", label: "Decisions", types: ["decision"] },
  { value: "team", label: "Team communication", types: ["team"] },
  { value: "instructor", label: "Instructor actions", types: ["note", "clock", "simulation"] },
];

/** Presentational timeline list (unit-tested). */
export function TimelineList({ events, onDecision }: { events: RoomEvent[]; onDecision?: (decisionId: string) => void }) {
  const rows = events.map((e) => ({ e, v: describeEvent(e) })).filter((r) => r.v !== null);
  if (!rows.length) return <p className="py-6 text-center text-xs text-muted">No events match the filters.</p>;
  return (
    <ol className="relative ml-3 border-l border-line" aria-label="Exercise timeline">
      {rows.map(({ e, v }) => {
        if (!v) return null;
        const Icon = v.icon;
        const decisionId = e.event_type === "decision.submitted" ? String((e.payload as Record<string, unknown>).decision_id ?? "") : "";
        return (
          <li key={`${e.seq}`} className="relative py-1.5 pl-5" data-testid="timeline-row">
            <span className="absolute -left-[7px] top-2.5 flex size-3.5 items-center justify-center rounded-full border border-line bg-panel">
              <Icon className={cn("size-2.5", toneText[v.tone])} aria-hidden />
            </span>
            <div className="flex items-baseline gap-3">
              <span className="w-14 shrink-0 font-mono text-[11px] tabular text-subtle">{formatSimTime(e.sim_time)}</span>
              <div className="min-w-0">
                {decisionId && onDecision ? (
                  <button type="button" className="text-left text-xs text-accent hover:underline" onClick={() => onDecision(decisionId)}>
                    {v.title}
                  </button>
                ) : (
                  <p className="text-xs">{v.title}</p>
                )}
                {v.detail && <p className="text-[11px] text-muted">{v.detail}</p>}
              </div>
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function AarTimeline({
  roomId,
  participants,
  channels,
  onDecision,
}: {
  roomId: string;
  participants: { participant_id: string; callsign: string }[];
  channels: string[];
  onDecision: (id: string) => void;
}) {
  const [type, setType] = useState("");
  const [participant, setParticipant] = useState("");
  const [channel, setChannel] = useState("");
  const types = TYPE_FILTERS.find((t) => t.value === type)?.types;
  const q = useTimeline(roomId, { event_type: types, participant_id: participant || undefined, channel_key: channel || undefined });

  return (
    <div className="space-y-3">
      <div className="grid gap-2 sm:grid-cols-3">
        <Select aria-label="Filter by event type" value={type} onChange={(e) => setType(e.target.value)}>
          {TYPE_FILTERS.map((t) => (
            <option key={t.value} value={t.value}>
              {t.label}
            </option>
          ))}
        </Select>
        <Select aria-label="Filter by participant" value={participant} onChange={(e) => setParticipant(e.target.value)}>
          <option value="">All participants</option>
          {participants.map((p) => (
            <option key={p.participant_id} value={p.participant_id}>
              {p.callsign}
            </option>
          ))}
        </Select>
        <Select aria-label="Filter by channel" value={channel} onChange={(e) => setChannel(e.target.value)}>
          <option value="">All channels</option>
          {channels.map((c) => (
            <option key={c} value={c}>
              {c}
            </option>
          ))}
        </Select>
      </div>
      <div className="max-h-[36rem] overflow-y-auto pr-1">
        {q.isLoading ? (
          <LoadingBlock rows={5} />
        ) : (
          <TimelineList events={(q.data?.events ?? []).filter((e) => e.event_type !== "metrics.updated")} onDecision={onDecision} />
        )}
      </div>
      {q.data && <p className="text-[11px] text-subtle">{q.data.count} events (append-only audit stream)</p>}
    </div>
  );
}
