"use client";

import { formatSimTime } from "@fogroom/shared";
import { Check, Clock, Radio } from "lucide-react";
import { PriorityBadge, ReliabilityBadge } from "@/components/status/indicators";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/feedback";
import type { TraineeMessage } from "@/lib/types";
import { cn } from "@/lib/utils";

export function InfoCard({ message, simTime, onAck }: { message: TraineeMessage; simTime: number; onAck?: (id: string) => void }) {
  const fresh = message.received_sim_time !== null && simTime - message.received_sim_time < 30;
  const age = message.received_sim_time !== null ? message.received_sim_time - message.report_sim_time : 0;
  return (
    <article
      className={cn(
        "rounded-lg border bg-panel-2 p-3 animate-fr-in",
        message.priority === "CRITICAL" ? "border-crit/50" : fresh ? "border-accent/50" : "border-line",
      )}
      aria-label={message.title}
      data-testid="info-card"
    >
      <header className="flex flex-wrap items-start justify-between gap-2">
        <h3 className="text-sm font-semibold leading-snug">{message.title}</h3>
        <div className="flex flex-wrap gap-1">
          {fresh && <span className="rounded bg-accent-soft px-1.5 py-0.5 text-[10px] font-semibold uppercase text-accent">New</span>}
          <PriorityBadge priority={message.priority} />
        </div>
      </header>
      <p className="mt-2 text-sm leading-relaxed text-fg/90">{message.content}</p>
      <footer className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-[11px] text-muted">
        <span className="font-medium text-fg/80">{message.source}</span>
        <ReliabilityBadge reliability={message.reliability} />
        <span className="flex items-center gap-1">
          <Radio className="size-3" aria-hidden /> {message.channel_name}
        </span>
        <span className="flex items-center gap-1 font-mono" title="Time received (report originated at the second time)">
          <Clock className="size-3" aria-hidden /> {formatSimTime(message.received_sim_time)}
          {age >= 5 && <span className="text-warn">(report {formatSimTime(message.report_sim_time)})</span>}
        </span>
        {onAck && (
          <Button
            size="sm"
            variant={message.acknowledged ? "ghost" : "secondary"}
            className="ml-auto h-7"
            disabled={message.acknowledged}
            onClick={() => onAck(message.id)}
          >
            <Check aria-hidden /> {message.acknowledged ? "Acknowledged" : "Acknowledge"}
          </Button>
        )}
      </footer>
    </article>
  );
}

export function InfoFeed({ messages, simTime, onAck }: { messages: TraineeMessage[]; simTime: number; onAck?: (id: string) => void }) {
  if (!messages.length)
    return <EmptyState title="No information received yet" description="Reports appear here only when they actually reach you." />;
  return (
    <div className="space-y-3" aria-live="polite">
      {messages.map((m) => (
        <InfoCard key={m.id} message={m} simTime={simTime} onAck={onAck} />
      ))}
    </div>
  );
}
