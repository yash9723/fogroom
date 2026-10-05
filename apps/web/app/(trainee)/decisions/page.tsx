"use client";

import { formatSimTime } from "@fogroom/shared";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useTraineeRoomId } from "@/components/trainee/use-trainee-room";
import { useTraineeState } from "@/features/live";

export default function DecisionLogPage() {
  const { roomId, loading } = useTraineeRoomId();
  const q = useTraineeState(roomId ?? undefined);
  if (loading || (roomId && !q.data)) return <LoadingBlock rows={5} />;
  if (!roomId || !q.data) return <EmptyState title="No active exercise" />;
  const points = q.data.decision_points;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow={q.data.room.scenario_name} title="Decision log" description="Your decisions, confidence and rationale." />
      {!points.length ? (
        <Card>
          <EmptyState title="No decisions requested yet" />
        </Card>
      ) : (
        <div className="space-y-3">
          {points.map((dp) => (
            <Card key={dp.id} className="p-4">
              <div className="flex items-center justify-between gap-2">
                <h2 className="text-sm font-semibold">{dp.title}</h2>
                {dp.my_decision ? <Badge tone="ok">Submitted</Badge> : dp.status === "OPEN" ? <Badge tone="warn">Open</Badge> : <Badge tone="crit">Missed</Badge>}
              </div>
              <p className="mt-1 text-xs text-muted">{dp.prompt}</p>
              {dp.my_decision && (
                <dl className="mt-3 grid grid-cols-[120px_1fr] gap-y-1 text-xs">
                  <dt className="text-muted">Decision</dt>
                  <dd>{dp.options.find((o) => o.key === dp.my_decision?.selected_option)?.label ?? dp.my_decision.decision_text}</dd>
                  <dt className="text-muted">Confidence</dt>
                  <dd className="font-mono">{dp.my_decision.confidence}%</dd>
                  <dt className="text-muted">Submitted</dt>
                  <dd className="font-mono">
                    {formatSimTime(dp.my_decision.submitted_sim_time)} ({(dp.my_decision.response_time_ms / 1000).toFixed(0)}s after opening)
                  </dd>
                  <dt className="text-muted">Rationale</dt>
                  <dd className="italic">{dp.my_decision.rationale ?? "-"}</dd>
                </dl>
              )}
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
