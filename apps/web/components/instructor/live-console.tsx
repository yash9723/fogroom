"use client";

import { formatSimTime } from "@fogroom/shared";
import { Activity, FastForward, ListChecks, Network, SlidersHorizontal, Users, Vote } from "lucide-react";
import { useMemo } from "react";
import { CommGraph } from "@/components/network/comm-graph";
import { SimClock } from "@/components/sim-clock";
import { ChannelRow, ConnectionIndicator } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { ErrorState, LoadingBlock } from "@/components/ui/feedback";
import { useInstructorState, useOpenDecisionPoint, useTriggerEvent } from "@/features/live";
import { useAdvanceClock, useLifecycle } from "@/features/rooms";
import { ControlPanel, LifecycleControls } from "./control-panel";
import { EventFeed } from "./event-feed";
import { ParticipantPanel } from "./participant-panel";
import { ScenarioTimeline } from "./scenario-timeline";

export function LiveConsole({ roomId }: { roomId: string }) {
  const q = useInstructorState(roomId);
  const lifecycle = useLifecycle(roomId);
  const advance = useAdvanceClock(roomId);
  const fire = useTriggerEvent(roomId);
  const openDp = useOpenDecisionPoint(roomId);
  const state = q.data;

  const blackoutIds = useMemo(() => {
    const ids = new Set<string>();
    state?.disruptions
      .filter((d) => d.is_active && d.disruption_type === "BLACKOUT")
      .forEach((d) => (d.target_participant_ids.length ? d.target_participant_ids : state.participants.map((p) => p.id)).forEach((id) => ids.add(id)));
    return ids;
  }, [state]);

  if (q.error) return <ErrorState message={q.error.message} />;
  if (!state) return <LoadingBlock rows={8} />;

  const nextScheduled = state.timeline
    .filter((t) => t.status === "UPCOMING" && t.scheduled_sim_time !== null && t.scheduled_sim_time > state.sim_time)
    .sort((a, b) => (a.scheduled_sim_time ?? 0) - (b.scheduled_sim_time ?? 0))[0];

  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <Card className="flex flex-wrap items-center justify-between gap-4 px-4 py-3">
        <div className="flex flex-wrap items-center gap-6">
          <SimClock
            simTime={state.sim_time}
            status={state.room.status}
            timeScale={state.room.time_scale}
            fetchedAt={q.dataUpdatedAt}
            phase={state.phase?.name}
          />
          <div className="hidden h-10 w-px bg-line md:block" />
          <div>
            <div className="text-sm font-semibold">{state.room.name}</div>
            <div className="text-xs text-muted">
              Room <span className="font-mono text-accent">{state.room.room_code}</span> · {state.room.scenario_name}
            </div>
          </div>
          <ConnectionIndicator roomId={roomId} />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {nextScheduled && (
            <Button
              variant="ghost"
              onClick={() => advance.mutate(nextScheduled.scheduled_sim_time as number)}
              loading={advance.isPending}
              title="Fast-forward the simulation clock to the next scheduled item"
              data-testid="skip-next"
            >
              <FastForward aria-hidden /> Next: {nextScheduled.title} ({formatSimTime(nextScheduled.scheduled_sim_time)})
            </Button>
          )}
          <LifecycleControls status={state.room.status} busy={lifecycle.isPending} onAction={(a) => lifecycle.mutate(a)} />
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[minmax(300px,1fr)_minmax(360px,1.3fr)_minmax(340px,1.1fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader title="Participants" description="Live information-state metrics" icon={<Users />} />
            <ParticipantPanel participants={state.participants} blackoutIds={blackoutIds} />
          </Card>
          <Card>
            <CardHeader title="Communication network" icon={<Network />} />
            <div className="space-y-2 p-3">
              <CommGraph
                participants={state.participants.map((p) => ({ id: p.id, callsign: p.callsign, blackout: blackoutIds.has(p.id) }))}
                channels={state.channels}
              />
              <div className="grid grid-cols-2 gap-2">
                {state.channels.map((c) => (
                  <ChannelRow key={c.id} channel={c} dense />
                ))}
              </div>
            </div>
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Scenario timeline" description={`${state.timeline.filter((t) => t.status !== "UPCOMING").length}/${state.timeline.length} fired`} icon={<ListChecks />} />
            <ScenarioTimeline
              items={state.timeline}
              simTime={state.sim_time}
              disabled={fire.isPending || openDp.isPending || advance.isPending}
              onFire={(key) => fire.mutate({ template_key: key })}
              onOpenDecision={(key) => openDp.mutate(key)}
              onSkipTo={(t) => advance.mutate(t)}
            />
          </Card>
          <Card>
            <CardHeader title="Event feed" description="Global truth - instructor only" icon={<Activity />} />
            <EventFeed events={state.events} />
          </Card>
        </div>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Controls" icon={<SlidersHorizontal />} />
            <div className="p-3">
              <ControlPanel state={state} roomId={roomId} />
            </div>
          </Card>
          <Card>
            <CardHeader title="Recent decisions" icon={<Vote />} />
            {state.decisions.length === 0 ? (
              <p className="px-4 py-6 text-center text-xs text-muted">No decisions submitted yet</p>
            ) : (
              <ul className="max-h-80 divide-y divide-line overflow-y-auto">
                {state.decisions.map((d) => (
                  <li key={d.id} className="px-4 py-2.5 text-xs">
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-mono font-semibold text-accent">{d.callsign}</span>
                      <span className="font-mono text-subtle">{formatSimTime(d.submitted_sim_time)}</span>
                    </div>
                    <div className="mt-1 font-medium">{d.selected_label ?? d.decision_text}</div>
                    <div className="mt-0.5 text-muted">
                      {d.decision_point_title} · <Badge tone="accent">{d.confidence}% confidence</Badge> · {(d.response_time_ms / 1000).toFixed(0)}s
                    </div>
                    {d.rationale && <p className="mt-1 italic text-muted">“{d.rationale}”</p>}
                  </li>
                ))}
              </ul>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
