"use client";

import { formatSimTime } from "@fogroom/shared";
import {
  AlertTriangle,
  BookOpenCheck,
  Download,
  Eye,
  FileText,
  Lightbulb,
  ListTree,
  NotebookPen,
  Printer,
  RefreshCw,
  Users,
  Vote,
  Waypoints,
} from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { WithQueryId } from "@/components/layout/with-query-id";
import { routes } from "@/lib/routes";
import { AarTimeline } from "@/components/aar/aar-timeline";
import { CommsAnalysis } from "@/components/aar/comms-analysis";
import { DecisionInspector } from "@/components/aar/decision-inspector";
import { ParticipantComparison } from "@/components/aar/participant-comparison";
import { ReplayPanel, type ReplayView } from "@/components/aar/replay-panel";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { downloadAarPdf, useAar, useGenerateAar } from "@/features/aar";
import { useRoom } from "@/features/rooms";
import type { AarReport } from "@/lib/types";
import { cn, scoreTone, uncertaintyTone } from "@/lib/utils";

function Overview({ report, narrative, source }: { report: AarReport; narrative: string | null; source: string }) {
  const t = report.team;
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        <StatCard label="Team score" value={t.team_score.toFixed(0)} hint="Experimental metric" tone={scoreTone(t.team_score)} />
        <StatCard label="Decision agreement" value={`${t.decision_agreement.toFixed(0)}%`} tone={scoreTone(t.decision_agreement)} />
        <StatCard label="Avg confidence" value={`${t.average_confidence.toFixed(0)}%`} />
        <StatCard label="Avg uncertainty at decision" value={t.average_uncertainty_at_decision.toFixed(0)} tone={uncertaintyTone(t.average_uncertainty_at_decision)} />
        <StatCard label="Avg response" value={`${t.average_response_time_s.toFixed(0)}s`} hint="simulation time" />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader title="Exercise summary" icon={<FileText />} actions={<Badge tone={source === "AI" ? "violet" : "neutral"}>{source === "AI" ? "AI narrative" : "Template narrative"}</Badge>} />
          <CardBody className="space-y-3 text-sm leading-relaxed">
            <p>{report.summary}</p>
            {narrative && <p className="whitespace-pre-line text-muted">{narrative}</p>}
            <div className="flex flex-wrap gap-2 pt-1 text-xs">
              {Object.entries(t.delivery_status_counts).map(([k, v]) => (
                <Badge key={k} tone={k === "DROPPED" || k === "FAILED" ? "crit" : k === "ALTERED" ? "violet" : k === "DELIVERED" ? "ok" : "warn"}>
                  {k} {v}
                </Badge>
              ))}
            </div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Recommendations" icon={<Lightbulb />} />
          <CardBody>
            <ul className="list-disc space-y-1.5 pl-4 text-sm">
              {report.recommendations.map((r) => (
                <li key={r}>{r}</li>
              ))}
            </ul>
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader title="Participant comparison" description="Training Coordination Metric and other explainable scores" icon={<Users />} />
        <CardBody>
          <ParticipantComparison participants={report.participants} />
        </CardBody>
      </Card>
      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader title="Training objectives" icon={<BookOpenCheck />} />
          <CardBody className="space-y-4">
            {report.objectives.map((o) => (
              <div key={o.key}>
                <h3 className="text-sm font-semibold">{o.title}</h3>
                <ul className="mt-1 list-disc space-y-0.5 pl-4 text-xs text-muted">
                  {o.observations.map((x) => (
                    <li key={x}>{x}</li>
                  ))}
                </ul>
              </div>
            ))}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Instructor notes" icon={<NotebookPen />} />
          <CardBody>
            {report.notes.length === 0 ? (
              <p className="text-xs text-muted">No notes were recorded.</p>
            ) : (
              <ul className="space-y-2 text-sm">
                {report.notes.map((n, i) => (
                  <li key={i}>
                    <span className="mr-2 font-mono text-xs text-subtle">{n.label}</span>
                    {n.callsign && <Badge tone="accent" className="mr-2">{n.callsign}</Badge>}
                    {n.content}
                  </li>
                ))}
              </ul>
            )}
          </CardBody>
        </Card>
      </div>
      <details className="rounded-lg border border-line bg-panel p-4 text-xs text-muted">
        <summary className="cursor-pointer font-medium text-fg">How scores are calculated</summary>
        <p className="mt-2">{report.metric_disclaimer}</p>
        <ul className="mt-2 space-y-1 font-mono">
          {Object.entries(report.formulas).map(([k, v]) => (
            <li key={k}>
              <span className="text-accent">{k}</span> = {v}
            </li>
          ))}
        </ul>
      </details>
    </div>
  );
}

function DecisionAnalysis({ report, onInspect }: { report: AarReport; onInspect: (id: string) => void }) {
  const byPoint = new Map<string, AarReport["decisions"]>();
  report.decisions.forEach((d) => byPoint.set(d.decision_point_title, [...(byPoint.get(d.decision_point_title) ?? []), d]));
  if (!report.decisions.length) return <EmptyState title="No decisions were submitted" />;
  return (
    <div className="space-y-4">
      {[...byPoint.entries()].map(([title, list]) => (
        <Card key={title}>
          <CardHeader title={title} icon={<Vote />} actions={list[0].critical ? <Badge tone="crit">Critical decision</Badge> : null} />
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-line text-left text-xs text-muted">
                  <th className="px-4 py-2 font-medium">Who</th>
                  <th className="px-4 py-2 font-medium">Decision</th>
                  <th className="px-4 py-2 font-medium">Time</th>
                  <th className="px-4 py-2 font-medium">Confidence</th>
                  <th className="px-4 py-2 font-medium">Uncertainty</th>
                  <th className="px-4 py-2 font-medium">Quality*</th>
                  <th className="px-4 py-2 font-medium">Info gaps</th>
                  <th className="px-4 py-2" />
                </tr>
              </thead>
              <tbody className="divide-y divide-line">
                {list.map((d) => (
                  <tr key={d.id}>
                    <td className="px-4 py-2 font-mono text-accent">{d.callsign}</td>
                    <td className="px-4 py-2">
                      {d.selected_label ?? d.decision_text}
                      {d.rationale && <div className="text-xs italic text-muted">“{d.rationale}”</div>}
                    </td>
                    <td className="px-4 py-2 font-mono text-xs">{d.submitted_label}</td>
                    <td className="px-4 py-2 font-mono">{d.confidence}%</td>
                    <td className={cn("px-4 py-2 font-mono", { ok: "text-ok", warn: "text-warn", crit: "text-crit", off: "" }[uncertaintyTone(d.uncertainty_index)])}>
                      {d.uncertainty_index?.toFixed(0) ?? "-"}
                    </td>
                    <td className={cn("px-4 py-2 font-mono", { ok: "text-ok", warn: "text-warn", crit: "text-crit", off: "" }[scoreTone(d.decision_quality)])}>
                      {d.decision_quality.toFixed(0)}
                    </td>
                    <td className="px-4 py-2 text-xs">
                      {d.known_contradictions > 0 && (
                        <Badge tone="violet" className="mr-1">
                          <AlertTriangle aria-hidden /> {d.known_contradictions} conflict
                        </Badge>
                      )}
                      {d.missing_relevant.length > 0 && <Badge tone="crit">{d.missing_relevant.length} missing</Badge>}
                    </td>
                    <td className="px-4 py-2 text-right">
                      <Button size="sm" variant="secondary" onClick={() => onInspect(d.id)} data-testid={`inspect-${d.callsign}-${d.decision_point_key}`}>
                        <Eye aria-hidden /> Inspect
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </Card>
      ))}
      <p className="text-[11px] text-subtle">*Decision quality uses the scenario designer&apos;s rubric (truth alignment) - an experimental training metric.</p>
    </div>
  );
}

export default function AarPage() {
  return <WithQueryId render={(id) => <AarReportView key={id} roomId={id} />} />;
}

function AarReportView({ roomId }: { roomId: string }) {
  const room = useRoom(roomId);
  const aar = useAar(roomId);
  const generate = useGenerateAar(roomId);
  const [tab, setTab] = useState("overview");
  const [inspect, setInspect] = useState<string | null>(null);
  const [replayT, setReplayT] = useState<number | null>(null);
  const [view, setView] = useState<ReplayView>("truth");

  if (room.error) return <ErrorState message={room.error.message} />;
  if (room.isLoading || aar.isLoading) return <LoadingBlock rows={8} />;
  const r = room.data;
  if (!r) return null;

  const completed = r.status === "COMPLETED" || r.status === "ARCHIVED";
  const env = aar.data;
  const report = env?.report;
  const time = replayT ?? report?.exercise.duration_seconds ?? 0;

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        eyebrow="After Action Review"
        title={r.name}
        description={report ? `${report.exercise.scenario} · duration ${report.exercise.duration_label} · room ${r.room_code}` : r.scenario_name ?? undefined}
        actions={
          completed && (
            <>
              {env && (
                <>
                  <Button variant="secondary" asChild>
                    <Link href={routes.aarPrint(roomId)}>
                      <Printer aria-hidden /> Print view
                    </Link>
                  </Button>
                  <Button variant="secondary" onClick={() => downloadAarPdf(roomId, r.room_code)} data-testid="export-pdf">
                    <Download aria-hidden /> Export PDF
                  </Button>
                </>
              )}
              <Button variant={env ? "ghost" : "primary"} onClick={() => generate.mutate()} loading={generate.isPending} data-testid="generate-aar">
                <RefreshCw aria-hidden /> {env ? `Regenerate (v${env.version})` : "Generate AAR"}
              </Button>
            </>
          )
        }
      />

      {!completed ? (
        <Card>
          <EmptyState title="Exercise still running" description="The AAR becomes available once the exercise has ended." action={<Button asChild><Link href={routes.exercise(roomId)}>Open live console</Link></Button>} />
        </Card>
      ) : !report ? (
        <Card>
          <EmptyState
            icon={<FileText />}
            title="No AAR generated yet"
            description="Generating builds the report from the recorded event stream - history is never modified."
            action={
              <Button variant="primary" onClick={() => generate.mutate()} loading={generate.isPending}>
                Generate AAR
              </Button>
            }
          />
        </Card>
      ) : (
        <Tabs value={tab} onValueChange={setTab}>
          <TabsList>
            <TabsTrigger value="overview"><FileText aria-hidden /> Overview</TabsTrigger>
            <TabsTrigger value="replay" data-testid="tab-replay"><Eye aria-hidden /> Replay</TabsTrigger>
            <TabsTrigger value="decisions" data-testid="tab-decisions"><Vote aria-hidden /> Decisions</TabsTrigger>
            <TabsTrigger value="timeline"><ListTree aria-hidden /> Timeline</TabsTrigger>
            <TabsTrigger value="comms"><Waypoints aria-hidden /> Communications</TabsTrigger>
          </TabsList>
          <TabsContent value="overview">
            <Overview report={report} narrative={env.narrative} source={env.narrative_source} />
          </TabsContent>
          <TabsContent value="replay">
            <ReplayPanel roomId={roomId} report={report} time={time} onTime={setReplayT} view={view} onView={setView} />
          </TabsContent>
          <TabsContent value="decisions">
            <DecisionAnalysis report={report} onInspect={setInspect} />
          </TabsContent>
          <TabsContent value="timeline">
            <Card>
              <CardBody>
                <AarTimeline
                  roomId={roomId}
                  participants={report.participants}
                  channels={Array.from(new Set(report.channel_history.map((c) => c.channel)))}
                  onDecision={setInspect}
                />
              </CardBody>
            </Card>
          </TabsContent>
          <TabsContent value="comms">
            <Card>
              <CardBody>
                <CommsAnalysis roomId={roomId} report={report} />
              </CardBody>
            </Card>
          </TabsContent>
        </Tabs>
      )}

      <DecisionInspector
        roomId={roomId}
        decisionId={inspect}
        onClose={() => setInspect(null)}
        onReplay={(pid, t) => {
          setInspect(null);
          setView(pid);
          setReplayT(Math.round(t));
          setTab("replay");
        }}
      />
      {report && (
        <p className="mt-6 text-[11px] text-subtle">
          Generated {new Date(env.generated_at).toLocaleString()} · replay covers {formatSimTime(0)}–{report.exercise.duration_label}
        </p>
      )}
    </div>
  );
}
