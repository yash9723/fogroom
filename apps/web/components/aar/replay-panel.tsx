"use client";

import { formatSimTime } from "@fogroom/shared";
import { AlertTriangle, CheckCircle2, Eye, Globe2, XCircle } from "lucide-react";
import { useDeferredValue } from "react";
import { DeliveryStateBadge, ChannelStatusBadge, ReliabilityBadge } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState, LoadingBlock, Meter } from "@/components/ui/feedback";
import { Slider } from "@/components/ui/slider";
import { useInfoState } from "@/features/aar";
import type { AarReport, InfoItem, ParticipantInfoState, TruthInfoState } from "@/lib/types";
import { cn, scoreTone, uncertaintyTone } from "@/lib/utils";

export type ReplayView = "truth" | string;

function TimeTrack({
  duration,
  value,
  onChange,
  report,
}: {
  duration: number;
  value: number;
  onChange: (v: number) => void;
  report: AarReport;
}) {
  const pct = (t: number) => `${Math.min(100, (t / Math.max(duration, 1)) * 100)}%`;
  return (
    <div className="px-1">
      <div className="mb-1 flex items-center justify-between font-mono text-xs text-muted">
        <span>T+00:00</span>
        <span className="text-base font-semibold text-accent presentation-emphasis" data-testid="replay-time">
          {formatSimTime(value)}
        </span>
        <span>{formatSimTime(duration)}</span>
      </div>
      <div className="relative">
        <Slider
          value={[value]}
          min={0}
          max={Math.max(1, Math.ceil(duration))}
          step={1}
          thumbLabel="Replay time"
          onValueChange={([v]) => onChange(v)}
          data-testid="replay-slider"
        />
        <div className="pointer-events-none relative h-4" aria-hidden>
          {report.disruptions.map((d) => (
            <span
              key={d.id}
              className="absolute top-0 h-1 rounded bg-crit/60"
              style={{ left: pct(d.start_sim_time), width: pct((d.end_sim_time ?? duration) - d.start_sim_time) }}
            />
          ))}
          {report.decisions.map((d) => (
            <span key={d.id} className="absolute top-1.5 h-2.5 w-0.5 bg-accent" style={{ left: pct(d.submitted_sim_time) }} />
          ))}
        </div>
      </div>
      <div className="flex gap-4 text-[10px] text-muted">
        <span><span className="mr-1 inline-block h-2 w-0.5 bg-accent align-middle" />decision</span>
        <span><span className="mr-1 inline-block h-1 w-3 bg-crit/60 align-middle" />disruption</span>
      </div>
    </div>
  );
}

function ItemRow({ item, state }: { item: InfoItem; state: string }) {
  const altered = item.altered || item.status === "ALTERED";
  const effectiveState = state === "IN_FLIGHT" && item.eventual_outcome ? item.eventual_outcome : state;
  return (
    <li className="rounded-md border border-line bg-panel-2 px-3 py-2 text-xs" data-testid="replay-item">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <span className="mr-1.5 font-mono text-subtle">{item.label}</span>
          <span className="font-medium">{(altered && item.delivered_title) || item.title}</span>
        </div>
        <DeliveryStateBadge state={altered ? "ALTERED" : item.status === undefined ? "NOT_ADDRESSED" : effectiveState} />
      </div>
      <p className="mt-1 text-muted">{altered ? item.delivered_content : item.canonical_content}</p>
      <div className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 text-[10px] text-subtle">
        <span>{item.channel_name}</span>
        <span>created {formatSimTime(item.created_sim_time)}</span>
        {state === "RECEIVED" && item.received_sim_time !== undefined && item.received_sim_time !== null && (
          <span>received {formatSimTime(item.received_sim_time)}</span>
        )}
        {item.arrives_sim_time !== undefined && item.arrives_sim_time !== null && (
          <span className="text-warn">arrives {formatSimTime(item.arrives_sim_time)}</span>
        )}
        {item.fact_key && (
          <span>
            {item.fact_key}: <strong className={cn(altered && "text-violet")}>{item.delivered_fact_value ?? item.fact_value}</strong>
            {item.truth_value_at_t && ` (truth: ${item.truth_value_at_t})`}
          </span>
        )}
      </div>
      {item.reasons && item.reasons.length > 0 && state !== "RECEIVED" && (
        <p className="mt-1 text-[10px] text-muted">{item.reasons.join(" · ")}</p>
      )}
    </li>
  );
}

function Column({ title, items, state, tone }: { title: string; items: InfoItem[]; state: string; tone: "ok" | "warn" | "crit" | "off" }) {
  return (
    <section aria-label={title}>
      <h4 className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide">
        {title} <Badge tone={tone}>{items.length}</Badge>
      </h4>
      {items.length === 0 ? (
        <p className="text-xs text-subtle">None</p>
      ) : (
        <ul className="space-y-2">
          {items.map((i) => (
            <ItemRow key={i.message_id} item={i} state={state} />
          ))}
        </ul>
      )}
    </section>
  );
}

function ParticipantView({ s }: { s: ParticipantInfoState }) {
  const m = s.metrics;
  return (
    <div className="space-y-5" data-testid="participant-view">
      <div className="grid gap-4 md:grid-cols-[1fr_1.4fr]">
        <div className="grid grid-cols-2 gap-3 rounded-lg border border-line bg-panel-2 p-3">
          <Meter label="Uncertainty index" value={m.uncertainty_index} tone={uncertaintyTone(m.uncertainty_index)} />
          <Meter label="Completeness" value={m.information_completeness} tone={scoreTone(m.information_completeness)} />
          <Meter label="Reliability" value={m.information_reliability} tone={scoreTone(m.information_reliability)} />
          <Meter label="Comm health" value={m.communication_health} tone={scoreTone(m.communication_health)} />
          <p className="col-span-2 text-[11px] text-muted">
            Known contradictions: <strong className={m.known_contradictions ? "text-violet" : ""}>{m.known_contradictions}</strong>
            {s.blackout && <Badge tone="crit" className="ml-2">Blackout</Badge>}
          </p>
        </div>
        <div className="space-y-3">
          <div className="flex flex-wrap gap-1.5">
            {s.channels.map((c) => (
              <span key={c.id} className="flex items-center gap-1 rounded border border-line bg-panel-2 px-2 py-1 text-[11px]">
                {c.name} <ChannelStatusBadge status={c.status} />
              </span>
            ))}
          </div>
          <div>
            <h4 className="mb-1.5 text-xs font-semibold uppercase tracking-wide">Beliefs vs ground truth</h4>
            {s.beliefs.length === 0 ? (
              <p className="text-xs text-subtle">No factual reports held yet.</p>
            ) : (
              <ul className="space-y-1">
                {s.beliefs.map((b) => (
                  <li key={b.fact_key} className="flex items-center gap-2 text-xs">
                    {b.accurate ? (
                      <CheckCircle2 className="size-3.5 text-ok" aria-label="accurate" />
                    ) : (
                      <XCircle className="size-3.5 text-crit" aria-label="inaccurate" />
                    )}
                    <span className="text-muted">{b.label}:</span>
                    <strong>{b.believed_value}</strong>
                    {!b.accurate && <span className="text-crit">(truth: {b.truth_value})</span>}
                  </li>
                ))}
              </ul>
            )}
          </div>
          {s.contradictions.map((c) => (
            <div key={c.fact_key} className="rounded-md border border-violet/40 bg-[#211a3a]/60 p-2.5 text-xs" data-testid="replay-contradiction">
              <p className="flex items-center gap-1.5 font-medium text-violet">
                <AlertTriangle className="size-3.5" aria-hidden /> Contradictory reports: {c.label}
              </p>
              <ul className="mt-1 space-y-0.5 text-muted">
                {c.reports.map((r) => (
                  <li key={r.label}>
                    {r.label} “{r.value}” - {r.source} <ReliabilityBadge reliability={r.source_reliability} />
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>
      </div>
      <div className="grid gap-4 lg:grid-cols-3">
        <Column title="Known (received)" items={s.received} state="RECEIVED" tone="ok" />
        <Column title="In flight (not yet received)" items={s.pending} state="IN_FLIGHT" tone="warn" />
        <Column title="Dropped / never addressed" items={[...s.dropped, ...s.not_addressed]} state="DROPPED" tone="crit" />
      </div>
    </div>
  );
}

function TruthView({ s, callsigns }: { s: TruthInfoState; callsigns: string[] }) {
  return (
    <div className="space-y-5" data-testid="truth-view">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-lg border border-line bg-panel-2 p-3">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">Ground truth at this moment</h4>
          <ul className="space-y-1 text-xs">
            {s.truth.facts.map((f) => (
              <li key={f.key} className="flex justify-between gap-2">
                <span className="text-muted">{f.label}</span>
                <strong>{f.value ?? "-"}</strong>
              </li>
            ))}
          </ul>
        </div>
        <div className="rounded-lg border border-line bg-panel-2 p-3">
          <h4 className="mb-2 text-xs font-semibold uppercase tracking-wide">Each participant&apos;s picture</h4>
          <table className="w-full text-xs">
            <thead className="text-muted">
              <tr>
                <th className="text-left font-medium">Who</th>
                <th className="text-right font-medium">Uncertainty</th>
                <th className="text-right font-medium">Complete</th>
                <th className="text-right font-medium">Wrong beliefs</th>
              </tr>
            </thead>
            <tbody>
              {s.participants.map((p) => (
                <tr key={p.participant_id}>
                  <td className="py-0.5 font-mono text-accent">{p.callsign}</td>
                  <td className="text-right font-mono">{p.metrics.uncertainty_index.toFixed(0)}</td>
                  <td className="text-right font-mono">{p.metrics.information_completeness.toFixed(0)}%</td>
                  <td className={cn("text-right font-mono", p.inaccurate_beliefs.length > 0 && "text-crit")}>
                    {p.inaccurate_beliefs.length}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-xs" aria-label="Who received what">
          <thead className="bg-panel-2 text-muted">
            <tr>
              <th className="px-3 py-2 text-left font-medium">Information (canonical)</th>
              {callsigns.map((c) => (
                <th key={c} className="px-3 py-2 text-left font-mono font-medium">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {s.messages.map((m) => (
              <tr key={m.message_id}>
                <td className="px-3 py-2">
                  <span className="mr-1.5 font-mono text-subtle">{m.label}</span>
                  <span className="font-medium">{m.title}</span>
                  <div className="text-[10px] text-subtle">
                    {formatSimTime(m.created_sim_time)} · {m.channel_name}
                    {m.fact_key && ` · ${m.fact_key} = ${m.fact_value}`}
                  </div>
                </td>
                {callsigns.map((c) => {
                  const d = m.deliveries?.find((x) => x.callsign === c);
                  return (
                    <td key={c} className="px-3 py-2" data-testid={`truth-cell-${m.label}-${c}`}>
                      <DeliveryStateBadge state={d ? d.state : "NOT_ADDRESSED"} />
                    </td>
                  );
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

/** Information-State replay: scrub time and switch between global truth and each trainee. */
export function ReplayPanel({
  roomId,
  report,
  time,
  onTime,
  view,
  onView,
}: {
  roomId: string;
  report: AarReport;
  time: number;
  onTime: (t: number) => void;
  view: ReplayView;
  onView: (v: ReplayView) => void;
}) {
  const deferred = useDeferredValue(time);
  const q = useInfoState(roomId, view, deferred);
  const duration = report.exercise.duration_seconds;
  const callsigns = report.participants.map((p) => p.callsign);

  return (
    <Card>
      <CardHeader
        title="Information-State Replay"
        description="Global truth versus what each participant actually knew at the selected moment"
        icon={<Eye />}
      />
      <div className="space-y-4 p-4">
        <TimeTrack duration={duration} value={time} onChange={onTime} report={report} />
        <div className="flex flex-wrap gap-1" role="tablist" aria-label="Replay perspective">
          <button
            type="button"
            role="tab"
            aria-selected={view === "truth"}
            onClick={() => onView("truth")}
            className={cn(
              "flex items-center gap-1.5 rounded-md border px-3 py-1.5 text-xs font-medium",
              view === "truth" ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-fg",
            )}
            data-testid="view-truth"
          >
            <Globe2 className="size-3.5" aria-hidden /> Global Truth
          </button>
          {report.participants.map((p) => (
            <button
              type="button"
              key={p.participant_id}
              role="tab"
              aria-selected={view === p.participant_id}
              onClick={() => onView(p.participant_id)}
              className={cn(
                "rounded-md border px-3 py-1.5 font-mono text-xs font-medium",
                view === p.participant_id ? "border-accent bg-accent-soft text-accent" : "border-line text-muted hover:text-fg",
              )}
              data-testid={`view-${p.callsign}`}
            >
              {p.callsign} view
            </button>
          ))}
        </div>
        {q.isLoading && !q.data ? (
          <LoadingBlock rows={4} />
        ) : !q.data ? (
          <EmptyState title="No state available" />
        ) : q.data.view === "TRUTH" ? (
          <TruthView s={q.data} callsigns={callsigns} />
        ) : (
          <ParticipantView s={q.data} />
        )}
      </div>
    </Card>
  );
}
