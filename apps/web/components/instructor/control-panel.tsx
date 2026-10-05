"use client";

import { formatSimTime } from "@fogroom/shared";
import { Ban, GitBranch, Megaphone, NotebookPen, Pause, Play, RadioTower, RotateCcw, ShieldAlert, Signal, Square, Zap } from "lucide-react";
import { useState } from "react";
import { ChannelStatusBadge } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Slider } from "@/components/ui/slider";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAddNote,
  useChannelUpdate,
  useCreateDisruption,
  useEndDisruption,
  useInjectConflict,
  useSendNotice,
  useTriggerEvent,
  type ChannelPatch,
} from "@/features/live";
import type { Channel, Disruption, InstructorParticipant, InstructorState } from "@/lib/types";

/* ------------------------------------------------------------------ lifecycle */

export function LifecycleControls({
  status,
  onAction,
  busy,
}: {
  status: string;
  onAction: (action: "pause" | "resume" | "end") => void;
  busy?: boolean;
}) {
  const [confirming, setConfirming] = useState(false);
  return (
    <div className="flex flex-wrap items-center gap-2">
      {status === "RUNNING" ? (
        <Button variant="warn" onClick={() => onAction("pause")} loading={busy}>
          <Pause aria-hidden /> Pause
        </Button>
      ) : (
        <Button variant="success" onClick={() => onAction("resume")} loading={busy}>
          <Play aria-hidden /> Resume
        </Button>
      )}
      {confirming ? (
        <span className="flex items-center gap-1">
          <Button variant="danger" onClick={() => onAction("end")} data-testid="confirm-end">
            Confirm end
          </Button>
          <Button variant="ghost" onClick={() => setConfirming(false)}>
            Cancel
          </Button>
        </span>
      ) : (
        <Button variant="danger" onClick={() => setConfirming(true)} data-testid="end-exercise">
          <Square aria-hidden /> End exercise
        </Button>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------- channels */

export function ChannelControls({ channels, onChange }: { channels: Channel[]; onChange: (channelId: string, patch: ChannelPatch) => void }) {
  const [draft, setDraft] = useState<Record<string, number>>({});
  return (
    <ul className="space-y-2">
      {channels.map((c) => (
        <li key={c.id} className="rounded-md border border-line bg-panel-2 p-3" data-testid={`channel-${c.key}`}>
          <div className="flex items-center justify-between gap-2">
            <span className="text-xs font-semibold uppercase tracking-wide">{c.name}</span>
            <ChannelStatusBadge status={c.status} />
          </div>
          <div className="mt-2 flex items-center gap-3">
            <Slider
              value={[draft[c.id] ?? Math.round(c.reliability * 100)]}
              min={0}
              max={100}
              step={5}
              thumbLabel={`${c.name} reliability`}
              onValueChange={([v]) => setDraft((d) => ({ ...d, [c.id]: v }))}
              onValueCommit={([v]) => onChange(c.id, { reliability: v / 100, reason: "Reliability adjusted" })}
            />
            <span className="w-10 text-right font-mono text-xs tabular">{draft[c.id] ?? Math.round(c.reliability * 100)}%</span>
          </div>
          <div className="mt-2 flex flex-wrap gap-1">
            <Button
              size="sm"
              variant="warn"
              onClick={() => onChange(c.id, { status: "DEGRADED", reliability: Math.min(c.reliability, 0.6), latency_ms: Math.max(c.latency_ms, 8000), reason: "Degraded by instructor" })}
            >
              <Signal aria-hidden /> Degrade
            </Button>
            <Button size="sm" variant="danger" onClick={() => onChange(c.id, { status: "OFFLINE", reason: "Disabled by instructor" })}>
              <Ban aria-hidden /> Disable
            </Button>
            <Button size="sm" variant="success" onClick={() => onChange(c.id, { restore: true, reason: "Restored by instructor" })}>
              <RotateCcw aria-hidden /> Restore
            </Button>
          </div>
        </li>
      ))}
    </ul>
  );
}

/* ---------------------------------------------------------------- disruptions */

const DISRUPTIONS = [
  { value: "DELAY", label: "Delay communications" },
  { value: "DROPOUT", label: "Drop next message" },
  { value: "BLACKOUT", label: "Communications blackout" },
  { value: "RELIABILITY_REDUCTION", label: "Reduce reliability" },
  { value: "CHANNEL_FAILURE", label: "Channel failure" },
];

export type DisruptionDraft = {
  disruption_type: string;
  target_participant_ids: string[];
  target_channel_ids: string[];
  delay_seconds?: number;
  duration_seconds?: number;
  drop_next?: number;
};

export function DisruptionForm({
  participants,
  channels,
  onSubmit,
  busy,
}: {
  participants: { id: string; callsign: string }[];
  channels: { id: string; name: string }[];
  onSubmit: (draft: DisruptionDraft) => void;
  busy?: boolean;
}) {
  const [type, setType] = useState("DELAY");
  const [targets, setTargets] = useState<string[]>([]);
  const [chans, setChans] = useState<string[]>([]);
  const [delay, setDelay] = useState(60);
  const [duration, setDuration] = useState(120);

  const toggle = (list: string[], set: (v: string[]) => void, id: string) =>
    set(list.includes(id) ? list.filter((x) => x !== id) : [...list, id]);

  const submit = (e: React.FormEvent) => {
    e.preventDefault();
    const draft: DisruptionDraft = { disruption_type: type, target_participant_ids: targets, target_channel_ids: chans };
    if (type === "DELAY") draft.delay_seconds = delay;
    if (type === "DROPOUT") draft.drop_next = 1;
    if (type !== "DROPOUT" && duration > 0) draft.duration_seconds = duration;
    onSubmit(draft);
  };

  const needsChannel = type === "CHANNEL_FAILURE";
  return (
    <form onSubmit={submit} className="space-y-3" aria-label="Create disruption">
      <Field label="Disruption" htmlFor="dis-type">
        <Select id="dis-type" value={type} onChange={(e) => setType(e.target.value)}>
          {DISRUPTIONS.map((d) => (
            <option key={d.value} value={d.value}>
              {d.label}
            </option>
          ))}
        </Select>
      </Field>
      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-muted">Participants (none = everyone)</legend>
        <div className="flex flex-wrap gap-2">
          {participants.map((p) => (
            <label key={p.id} className="flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs">
              <input type="checkbox" checked={targets.includes(p.id)} onChange={() => toggle(targets, setTargets, p.id)} />
              {p.callsign}
            </label>
          ))}
        </div>
      </fieldset>
      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-muted">Channels {needsChannel ? "(required)" : "(none = all)"}</legend>
        <div className="flex flex-wrap gap-2">
          {channels.map((c) => (
            <label key={c.id} className="flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs">
              <input type="checkbox" checked={chans.includes(c.id)} onChange={() => toggle(chans, setChans, c.id)} />
              {c.name}
            </label>
          ))}
        </div>
      </fieldset>
      <div className="grid grid-cols-2 gap-3">
        {type === "DELAY" && (
          <Field label="Extra delay (s)" htmlFor="dis-delay">
            <Input id="dis-delay" type="number" min={1} max={3600} value={delay} onChange={(e) => setDelay(Number(e.target.value))} />
          </Field>
        )}
        {type !== "DROPOUT" && (
          <Field label="Duration (sim s, 0 = until ended)" htmlFor="dis-duration">
            <Input id="dis-duration" type="number" min={0} max={7200} value={duration} onChange={(e) => setDuration(Number(e.target.value))} />
          </Field>
        )}
      </div>
      <Button type="submit" variant="danger" loading={busy} disabled={needsChannel && chans.length === 0}>
        <ShieldAlert aria-hidden /> Start disruption
      </Button>
    </form>
  );
}

function ActiveDisruptions({ disruptions, participants, channels, onEnd }: { disruptions: Disruption[]; participants: InstructorParticipant[]; channels: Channel[]; onEnd: (id: string) => void }) {
  const active = disruptions.filter((d) => d.is_active);
  if (!active.length) return <p className="text-xs text-muted">No active disruptions.</p>;
  const name = (id: string) => participants.find((p) => p.id === id)?.callsign ?? channels.find((c) => c.id === id)?.name ?? id;
  return (
    <ul className="space-y-2">
      {active.map((d) => (
        <li key={d.id} className="flex items-start justify-between gap-2 rounded-md border border-crit/30 bg-crit-soft/40 p-2.5 text-xs">
          <div>
            <div className="font-medium">{d.disruption_type.replaceAll("_", " ")}</div>
            <div className="text-muted">
              {[...d.target_participant_ids, ...d.target_channel_ids].map(name).join(", ") || "Everyone"} · since {formatSimTime(d.start_sim_time)}
              {d.planned_end_sim_time ? ` → ${formatSimTime(d.planned_end_sim_time)}` : ""} · {d.source.toLowerCase()}
            </div>
          </div>
          <Button size="sm" variant="ghost" onClick={() => onEnd(d.id)}>
            End
          </Button>
        </li>
      ))}
    </ul>
  );
}

/* --------------------------------------------------------------------- inject */

function InjectPanel({ state, roomId }: { state: InstructorState; roomId: string }) {
  const trigger = useTriggerEvent(roomId);
  const conflict = useInjectConflict(roomId);
  const notice = useSendNotice(roomId);
  const [targets, setTargets] = useState<string[]>([]);
  const [variantIdx, setVariantIdx] = useState(0);
  const [noticeText, setNoticeText] = useState("");
  const [custom, setCustom] = useState({ title: "", content: "", channel_key: "", priority: "NORMAL", source_reliability: "MEDIUM" });

  const v = state.variants[variantIdx];
  const toggle = (id: string) => setTargets((t) => (t.includes(id) ? t.filter((x) => x !== id) : [...t, id]));

  return (
    <div className="space-y-5">
      <fieldset>
        <legend className="mb-1.5 text-xs font-medium text-muted">Target participants (none = everyone)</legend>
        <div className="flex flex-wrap gap-2">
          {state.participants.map((p) => (
            <label key={p.id} className="flex items-center gap-1.5 rounded border border-line px-2 py-1 text-xs">
              <input type="checkbox" checked={targets.includes(p.id)} onChange={() => toggle(p.id)} />
              {p.callsign}
            </label>
          ))}
        </div>
      </fieldset>

      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold"><GitBranch className="size-3.5 text-violet" aria-hidden /> Inject conflicting report</h3>
        {state.variants.length ? (
          <>
            <Select aria-label="Conflict variant" value={variantIdx} onChange={(e) => setVariantIdx(Number(e.target.value))}>
              {state.variants.map((x, i) => (
                <option key={`${x.event_key}-${x.variant_key}`} value={i}>
                  {x.fact_key}: “{x.variant_value}” (truth-side report says “{x.canonical_value}”)
                </option>
              ))}
            </Select>
            <Button
              size="sm"
              variant="secondary"
              loading={conflict.isPending}
              onClick={() =>
                v &&
                conflict.mutate({
                  fact_key: v.fact_key,
                  fact_value: v.variant_value,
                  title: "Conflicting field report",
                  content: v.content,
                  target_participant_ids: targets,
                  channel_key: null,
                })
              }
            >
              Inject conflict
            </Button>
          </>
        ) : (
          <p className="text-xs text-muted">This scenario defines no controlled variants.</p>
        )}
      </section>

      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold"><Zap className="size-3.5 text-accent" aria-hidden /> Custom information event</h3>
        <Input aria-label="Event title" placeholder="Title" value={custom.title} onChange={(e) => setCustom({ ...custom, title: e.target.value })} />
        <Textarea aria-label="Event content" placeholder="Report content" value={custom.content} onChange={(e) => setCustom({ ...custom, content: e.target.value })} />
        <div className="grid grid-cols-3 gap-2">
          <Select aria-label="Channel" value={custom.channel_key} onChange={(e) => setCustom({ ...custom, channel_key: e.target.value })}>
            <option value="">No channel (direct)</option>
            {state.channels.map((c) => (
              <option key={c.key} value={c.key}>{c.name}</option>
            ))}
          </Select>
          <Select aria-label="Priority" value={custom.priority} onChange={(e) => setCustom({ ...custom, priority: e.target.value })}>
            {["LOW", "NORMAL", "HIGH", "CRITICAL"].map((p) => <option key={p}>{p}</option>)}
          </Select>
          <Select aria-label="Source reliability" value={custom.source_reliability} onChange={(e) => setCustom({ ...custom, source_reliability: e.target.value })}>
            {["HIGH", "MEDIUM", "LOW"].map((p) => <option key={p}>{p}</option>)}
          </Select>
        </div>
        <Button
          size="sm"
          variant="secondary"
          disabled={!custom.title || !custom.content}
          loading={trigger.isPending}
          onClick={() =>
            trigger.mutate(
              { custom: { ...custom, channel_key: custom.channel_key || null, target_participant_ids: targets } },
              { onSuccess: () => setCustom({ ...custom, title: "", content: "" }) },
            )
          }
        >
          Send event (with degradation)
        </Button>
      </section>

      <section className="space-y-2">
        <h3 className="flex items-center gap-1.5 text-xs font-semibold"><Megaphone className="size-3.5 text-info" aria-hidden /> Simulation notice</h3>
        <Textarea aria-label="Notice text" placeholder="Notice to participants" value={noticeText} onChange={(e) => setNoticeText(e.target.value)} />
        <Button
          size="sm"
          variant="secondary"
          disabled={!noticeText}
          loading={notice.isPending}
          onClick={() => notice.mutate({ content: noticeText, target_participant_ids: targets }, { onSuccess: () => setNoticeText("") })}
        >
          Send notice
        </Button>
      </section>
    </div>
  );
}

/* ---------------------------------------------------------------------- notes */

function NotesPanel({ state, roomId }: { state: InstructorState; roomId: string }) {
  const add = useAddNote(roomId);
  const [text, setText] = useState("");
  const [pid, setPid] = useState("");
  return (
    <div className="space-y-3">
      <Textarea aria-label="Instructor note" value={text} onChange={(e) => setText(e.target.value)} placeholder="e.g. Bravo correctly identified conflicting infrastructure reports." />
      <div className="flex gap-2">
        <Select aria-label="About participant" value={pid} onChange={(e) => setPid(e.target.value)}>
          <option value="">General note</option>
          {state.participants.map((p) => (
            <option key={p.id} value={p.id}>{p.callsign}</option>
          ))}
        </Select>
        <Button
          variant="primary"
          disabled={!text.trim()}
          loading={add.isPending}
          onClick={() => add.mutate({ content: text, participant_id: pid || null }, { onSuccess: () => setText("") })}
        >
          <NotebookPen aria-hidden /> Save
        </Button>
      </div>
      <ul className="space-y-1.5">
        {[...state.notes].reverse().map((n) => (
          <li key={n.id} className="rounded border border-line bg-panel-2 px-2.5 py-1.5 text-xs">
            <span className="mr-2 font-mono text-subtle">{formatSimTime(n.sim_time)}</span>
            {n.content}
          </li>
        ))}
      </ul>
    </div>
  );
}

/* --------------------------------------------------------------- container */

export function ControlPanel({ state, roomId }: { state: InstructorState; roomId: string }) {
  const channel = useChannelUpdate(roomId);
  const createDisruption = useCreateDisruption(roomId);
  const endDisruption = useEndDisruption(roomId);
  const activeCount = state.disruptions.filter((d) => d.is_active).length;

  return (
    <Tabs defaultValue="channels">
      <TabsList className="flex w-full flex-wrap">
        <TabsTrigger value="channels"><RadioTower aria-hidden /> Channels</TabsTrigger>
        <TabsTrigger value="disruptions">
          <ShieldAlert aria-hidden /> Disrupt {activeCount > 0 && <Badge tone="crit">{activeCount}</Badge>}
        </TabsTrigger>
        <TabsTrigger value="inject"><Zap aria-hidden /> Inject</TabsTrigger>
        <TabsTrigger value="notes"><NotebookPen aria-hidden /> Notes</TabsTrigger>
      </TabsList>
      <TabsContent value="channels">
        <ChannelControls channels={state.channels} onChange={(channelId, patch) => channel.mutate({ channelId, patch })} />
      </TabsContent>
      <TabsContent value="disruptions" className="space-y-4">
        <ActiveDisruptions disruptions={state.disruptions} participants={state.participants} channels={state.channels} onEnd={(id) => endDisruption.mutate(id)} />
        <DisruptionForm
          participants={state.participants}
          channels={state.channels}
          busy={createDisruption.isPending}
          onSubmit={(draft) => createDisruption.mutate(draft)}
        />
      </TabsContent>
      <TabsContent value="inject">
        <InjectPanel state={state} roomId={roomId} />
      </TabsContent>
      <TabsContent value="notes">
        <NotesPanel state={state} roomId={roomId} />
      </TabsContent>
    </Tabs>
  );
}
