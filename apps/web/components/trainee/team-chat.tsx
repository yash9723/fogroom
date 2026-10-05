"use client";

import { formatSimTime } from "@fogroom/shared";
import { AlertTriangle, Send } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { useSendTeamMessage } from "@/features/live";
import type { TraineeState } from "@/lib/types";
import { cn } from "@/lib/utils";

/** Team communication - only works over channels that are actually available to you. */
export function TeamChat({ roomId, state, compact = false }: { roomId: string; state: TraineeState; compact?: boolean }) {
  const send = useSendTeamMessage(roomId);
  const usable = state.channels.filter((c) => c.status !== "OFFLINE");
  const [channel, setChannel] = useState("");
  const [recipient, setRecipient] = useState("");
  const [text, setText] = useState("");
  const chosen = channel || usable[0]?.key || state.channels[0]?.key || "";

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!text.trim() || !chosen) return;
    send.mutate(
      { channel_key: chosen, message: text.trim(), recipient_participant_id: recipient || null },
      { onSuccess: () => setText("") },
    );
  };

  const me = state.participant.id;
  return (
    <div className="flex flex-col">
      <ol className={cn("space-y-2 overflow-y-auto px-3 py-3", compact ? "max-h-56" : "max-h-[28rem]")} aria-label="Team messages">
        {state.team_messages.length === 0 && <li className="py-4 text-center text-xs text-muted">No team messages yet</li>}
        {state.team_messages.map((m) => {
          const mine = m.sender_participant_id === me;
          return (
            <li key={m.id} className={cn("flex", mine ? "justify-end" : "justify-start")}>
              <div
                className={cn(
                  "max-w-[85%] rounded-lg border px-3 py-2 text-xs",
                  mine ? "border-accent/30 bg-accent-soft" : "border-line bg-panel-2",
                  m.delivery_status === "FAILED" && "border-crit/40 bg-crit-soft",
                )}
              >
                <div className="mb-0.5 flex items-center gap-2 text-[10px] text-muted">
                  <span className="font-mono font-semibold text-fg/80">{m.sender_callsign}</span>
                  {m.recipient_callsign && <span>→ {m.recipient_callsign}</span>}
                  <span className="font-mono">{formatSimTime(m.sim_time)}</span>
                  {m.channel_key && <span>· {m.channel_key}</span>}
                </div>
                <p>{m.message}</p>
                {m.delivery_status === "FAILED" && (
                  <p className="mt-1 flex items-center gap-1 text-[10px] text-crit">
                    <AlertTriangle className="size-3" aria-hidden /> Not delivered: {m.failure_reason}
                  </p>
                )}
              </div>
            </li>
          );
        })}
      </ol>
      <form onSubmit={submit} className="space-y-2 border-t border-line p-3" aria-label="Send team message">
        {state.blackout && (
          <p className="flex items-center gap-1.5 text-xs text-crit" role="status">
            <AlertTriangle className="size-3.5" aria-hidden /> Your communications are blacked out.
          </p>
        )}
        <div className="grid grid-cols-2 gap-2">
          <Select aria-label="Channel" value={chosen} onChange={(e) => setChannel(e.target.value)} className="h-8 text-xs">
            {state.channels.map((c) => (
              <option key={c.key} value={c.key}>
                {c.name} {c.status === "OFFLINE" ? "(offline)" : c.status === "DEGRADED" ? "(degraded)" : ""}
              </option>
            ))}
          </Select>
          <Select aria-label="Recipient" value={recipient} onChange={(e) => setRecipient(e.target.value)} className="h-8 text-xs">
            <option value="">Whole team</option>
            {state.teammates.map((t) => (
              <option key={t.id} value={t.id}>
                {t.callsign}
              </option>
            ))}
          </Select>
        </div>
        <div className="flex gap-2">
          <Input aria-label="Message" value={text} onChange={(e) => setText(e.target.value)} maxLength={1000} placeholder="Share what you know…" className="h-8 text-xs" />
          <Button type="submit" size="sm" variant="primary" loading={send.isPending} disabled={!text.trim()} aria-label="Send">
            <Send />
          </Button>
        </div>
      </form>
    </div>
  );
}
