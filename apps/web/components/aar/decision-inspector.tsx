"use client";

import { formatSimTime } from "@fogroom/shared";
import { AlertTriangle, CheckCircle2, Clock, History, Inbox, SearchX, XCircle } from "lucide-react";
import { DeliveryStateBadge, ReliabilityBadge } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { ErrorState, LoadingBlock, Meter } from "@/components/ui/feedback";
import { useInspection } from "@/features/aar";
import type { InfoItem } from "@/lib/types";
import { scoreTone, uncertaintyTone } from "@/lib/utils";

function Section({ title, icon, count, children, tone = "neutral" }: { title: string; icon: React.ReactNode; count: number; children: React.ReactNode; tone?: "ok" | "warn" | "crit" | "violet" | "neutral" }) {
  return (
    <section className="rounded-lg border border-line" aria-label={title}>
      <h3 className="flex items-center gap-2 border-b border-line bg-panel-2 px-3 py-2 text-xs font-semibold uppercase tracking-wide [&_svg]:size-3.5">
        {icon} {title} <Badge tone={tone}>{count}</Badge>
      </h3>
      <div className="p-3">{count === 0 ? <p className="text-xs text-subtle">None</p> : children}</div>
    </section>
  );
}

function Item({ i, badge }: { i: InfoItem; badge?: string }) {
  const altered = i.altered || i.status === "ALTERED";
  return (
    <li className="text-xs">
      <div className="flex items-start justify-between gap-2">
        <span>
          <span className="mr-1 font-mono text-subtle">{i.label}</span>
          <span className="font-medium">{(altered && i.delivered_title) || i.title}</span>
        </span>
        {badge && <DeliveryStateBadge state={altered ? "ALTERED" : badge} />}
      </div>
      <p className="text-muted">{altered ? i.delivered_content : i.canonical_content}</p>
      <p className="text-[10px] text-subtle">
        {i.source} · {i.channel_name} · created {formatSimTime(i.created_sim_time)}
        {i.received_sim_time ? ` · received ${formatSimTime(i.received_sim_time)}` : ""}
        {i.arrives_sim_time ? ` · arrived ${formatSimTime(i.arrives_sim_time)}` : ""}
        {i.delay_seconds && i.delay_seconds >= 5 ? ` · +${i.delay_seconds.toFixed(0)}s` : ""}
      </p>
    </li>
  );
}

export function DecisionInspector({
  roomId,
  decisionId,
  onClose,
  onReplay,
}: {
  roomId: string;
  decisionId: string | null;
  onClose: () => void;
  onReplay?: (participantId: string, t: number) => void;
}) {
  const q = useInspection(roomId, decisionId);
  const d = q.data;
  return (
    <Dialog open={Boolean(decisionId)} onOpenChange={(o) => !o && onClose()}>
      <DialogContent wide title={d ? `${d.participant.callsign} · ${d.decision_point.title}` : "Decision inspection"} description="What this participant knew - and did not know - when deciding">
        {q.error ? (
          <ErrorState message={q.error.message} />
        ) : !d ? (
          <LoadingBlock rows={6} />
        ) : (
          <div className="space-y-4" data-testid="decision-inspection">
            <div className="grid gap-4 md:grid-cols-[1.3fr_1fr]">
              <div className="rounded-lg border border-accent/30 bg-accent-soft/40 p-3">
                <div className="text-xs uppercase tracking-wide text-muted">Decision</div>
                <div className="mt-1 text-base font-semibold">{d.decision.selected_label ?? d.decision.decision_text}</div>
                <dl className="mt-2 grid grid-cols-[110px_1fr] gap-y-1 text-xs">
                  <dt className="text-muted">Participant</dt>
                  <dd className="font-mono text-accent">{d.participant.callsign}</dd>
                  <dt className="text-muted">Timestamp</dt>
                  <dd className="font-mono">{formatSimTime(d.decision.submitted_sim_time)}</dd>
                  <dt className="text-muted">Response time</dt>
                  <dd className="font-mono" data-testid="inspection-response-time">{(d.decision.response_time_ms / 1000).toFixed(1)}s</dd>
                  <dt className="text-muted">Confidence</dt>
                  <dd className="font-mono" data-testid="inspection-confidence">{d.decision.confidence}%</dd>
                  <dt className="text-muted">Rationale</dt>
                  <dd className="italic" data-testid="inspection-rationale">{d.decision.rationale ?? "-"}</dd>
                </dl>
              </div>
              <div className="grid grid-cols-2 gap-3 rounded-lg border border-line bg-panel-2 p-3">
                <Meter label="Uncertainty index" value={d.metrics.uncertainty_index} tone={uncertaintyTone(d.metrics.uncertainty_index)} />
                <Meter label="Completeness" value={d.metrics.information_completeness} tone={scoreTone(d.metrics.information_completeness)} />
                <Meter label="Decision quality*" value={d.decision.decision_quality} tone={scoreTone(d.decision.decision_quality)} />
                <Meter label="Calibration" value={d.decision.calibration} tone={scoreTone(d.decision.calibration)} />
                <p className="col-span-2 text-[10px] text-subtle" data-testid="inspection-uncertainty">
                  Uncertainty score {d.metrics.uncertainty_index.toFixed(0)} · *scenario-designer rubric, experimental
                </p>
              </div>
            </div>

            {onReplay && (
              <Button size="sm" variant="secondary" onClick={() => onReplay(d.participant.id, d.snapshot_time)}>
                <History aria-hidden /> Replay {d.participant.callsign}&apos;s view at {formatSimTime(d.snapshot_time)}
              </Button>
            )}

            <div className="grid gap-3 lg:grid-cols-2">
              <Section title="Available information" icon={<Inbox className="text-ok" />} count={d.available_information.length} tone="ok">
                <ul className="space-y-2">{d.available_information.map((i) => <Item key={i.message_id} i={i} badge="RECEIVED" />)}</ul>
              </Section>
              <Section
                title="Missing information"
                icon={<SearchX className="text-crit" />}
                tone="crit"
                count={d.missing_information.dropped.length + d.missing_information.not_addressed.length + d.missing_information.in_flight.length}
              >
                <ul className="space-y-2">
                  {d.missing_information.dropped.map((i) => <Item key={i.message_id} i={i} badge="DROPPED" />)}
                  {d.missing_information.in_flight.map((i) => <Item key={i.message_id} i={i} badge={i.eventual_outcome ?? "IN_FLIGHT"} />)}
                  {d.missing_information.not_addressed.map((i) => <Item key={i.message_id} i={i} badge="NOT_ADDRESSED" />)}
                </ul>
              </Section>
              <Section
                title="Delayed information"
                icon={<Clock className="text-warn" />}
                tone="warn"
                count={d.delayed_information.arrived_late.length + d.delayed_information.arrived_after_decision.length}
              >
                <ul className="space-y-2">
                  {d.delayed_information.arrived_after_decision.map((i) => <Item key={i.message_id} i={i} badge="DELIVERED_LATER" />)}
                  {d.delayed_information.arrived_late.map((i) => <Item key={i.message_id} i={i} badge="DELAYED" />)}
                </ul>
              </Section>
              <Section title="Conflicting information" icon={<AlertTriangle className="text-violet" />} tone="violet" count={d.conflicting_information.length}>
                <ul className="space-y-2">
                  {d.conflicting_information.map((c) => (
                    <li key={c.fact_key} className="text-xs">
                      <div className="font-medium text-violet">{c.label}</div>
                      <ul className="mt-1 space-y-1">
                        {c.reports.map((r) => (
                          <li key={r.label} className="flex flex-wrap items-center gap-2 text-muted">
                            <span className="font-mono text-subtle">{r.label}</span> “{r.value}” · {r.source} <ReliabilityBadge reliability={r.source_reliability} />
                          </li>
                        ))}
                      </ul>
                    </li>
                  ))}
                </ul>
              </Section>
            </div>

            <section className="rounded-lg border border-line p-3">
              <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide">Beliefs at decision time vs ground truth</h3>
              {d.beliefs.length === 0 ? (
                <p className="text-xs text-subtle">No factual reports held.</p>
              ) : (
                <ul className="grid gap-1 sm:grid-cols-2">
                  {d.beliefs.map((b) => (
                    <li key={b.fact_key} className="flex items-center gap-2 text-xs">
                      {b.accurate ? <CheckCircle2 className="size-3.5 text-ok" aria-label="accurate" /> : <XCircle className="size-3.5 text-crit" aria-label="inaccurate" />}
                      <span className="text-muted">{b.label}:</span> <strong>{b.believed_value}</strong>
                      {!b.accurate && <span className="text-crit">truth: {b.truth_value}</span>}
                    </li>
                  ))}
                </ul>
              )}
            </section>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
