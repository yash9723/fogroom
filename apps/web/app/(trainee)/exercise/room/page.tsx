"use client";

import type { RoomEvent } from "@fogroom/shared";
import { CheckCircle2, Hourglass, Inbox, Map as MapIcon, MessagesSquare, Radio, Target, Vote } from "lucide-react";
import { useEffect } from "react";
import { WithQueryId } from "@/components/layout/with-query-id";
import { toast } from "sonner";
import { OpsMap } from "@/components/map/ops-map";
import { ChannelRow } from "@/components/status/indicators";
import { DecisionForm } from "@/components/trainee/decision-form";
import { InfoFeed } from "@/components/trainee/info-feed";
import { TeamChat } from "@/components/trainee/team-chat";
import { TraineeTopbar } from "@/components/trainee/trainee-topbar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/feedback";
import { useAcknowledge, useSubmitDecision, useTraineeState } from "@/features/live";
import { qk, useSetReady } from "@/features/rooms";
import { useRoomSocket } from "@/hooks/use-room-socket";
import { useSimClock } from "@/hooks/use-sim-clock";
import { useUiStore } from "@/lib/ui-store";

function notify(e: RoomEvent) {
  const p = e.payload as Record<string, unknown>;
  switch (e.event_type) {
    case "message.delivered":
      toast(`New report: ${String(p.title)}`, { description: String(p.channel_name ?? "") });
      break;
    case "decision.requested":
      toast.warning(`Decision required: ${String(p.title)}`);
      break;
    case "channel.updated":
      toast(`${String(p.name)} is now ${String(p.status).toLowerCase()}`);
      break;
    case "simulation.paused":
      toast.warning("Simulation paused by instructor");
      break;
    case "simulation.resumed":
      toast.success("Simulation resumed");
      break;
    case "simulation.completed":
      toast("Exercise completed");
      break;
    case "comms.changed":
      toast.warning("Your communications status changed");
      break;
  }
}

export default function TraineeExercisePage() {
  return <WithQueryId render={(id) => <TraineeExercise key={id} roomId={id} />} />;
}

function TraineeExercise({ roomId }: { roomId: string }) {
  const setActive = useUiStore((s) => s.setActiveRoomId);
  const q = useTraineeState(roomId);
  const submit = useSubmitDecision(roomId);
  const ack = useAcknowledge(roomId);
  const ready = useSetReady(roomId);
  useRoomSocket(roomId, { invalidate: [qk.trainee(roomId)], onEvent: notify });
  const state = q.data;
  const sim = useSimClock(state?.room.sim_time, state?.room.status, state?.room.time_scale ?? 1, q.dataUpdatedAt);

  useEffect(() => setActive(roomId), [roomId, setActive]);

  if (q.error) return <ErrorState message={q.error.message} />;
  if (!state) return <LoadingBlock rows={8} />;

  if (state.room.status === "LOBBY") {
    return (
      <Card className="mx-auto max-w-xl">
        <EmptyState
          icon={<Hourglass />}
          title={`Waiting for ${state.room.scenario_name} to start`}
          description={`You are ${state.participant.callsign} - ${state.participant.role_name ?? "role pending"}. Your instructor will start the exercise.`}
          action={
            <Button variant="primary" onClick={() => ready.mutate(true)} loading={ready.isPending}>
              <CheckCircle2 aria-hidden /> I am ready
            </Button>
          }
        />
      </Card>
    );
  }

  const open = state.decision_points.filter((d) => d.status === "OPEN" && !d.my_decision);
  const done = state.decision_points.filter((d) => d.my_decision);
  const ended = state.room.status === "COMPLETED" || state.room.status === "ARCHIVED";

  return (
    <div className="mx-auto max-w-[1600px] space-y-4">
      <TraineeTopbar state={state} fetchedAt={q.dataUpdatedAt} />
      {ended && (
        <div role="status" className="rounded-lg border border-line bg-panel-2 px-4 py-3 text-sm">
          The exercise has ended. Your instructor will run the After Action Review.
        </div>
      )}
      <div className="grid gap-4 xl:grid-cols-[minmax(320px,1fr)_minmax(380px,1.25fr)_minmax(300px,0.9fr)]">
        <div className="space-y-4">
          <Card>
            <CardHeader title="Active task" icon={<Target />} description={state.room.phase?.name} />
            <CardBody className="space-y-3 text-sm">
              <p className="text-muted">{state.participant.role_description}</p>
              <ul className="list-disc space-y-1 pl-4 text-xs text-fg/80">
                {state.participant.role_objectives.map((o) => (
                  <li key={o}>{o}</li>
                ))}
              </ul>
            </CardBody>
          </Card>
          <Card data-testid="decision-panel">
            <CardHeader title="Decisions" icon={<Vote />} actions={open.length ? <Badge tone="warn">{open.length} open</Badge> : null} />
            <CardBody className="space-y-6">
              {open.map((dp) => (
                <DecisionForm
                  key={dp.id}
                  point={dp}
                  simTime={sim}
                  onSubmit={async (values) => {
                    await submit.mutateAsync({ key: dp.key, body: values });
                  }}
                />
              ))}
              {!open.length && <p className="text-xs text-muted">No decision is currently requested from you.</p>}
              {done.length > 0 && (
                <ul className="space-y-2 border-t border-line pt-3">
                  {done.map((dp) => (
                    <li key={dp.id} className="text-xs">
                      <CheckCircle2 className="mr-1 inline size-3.5 text-ok" aria-hidden />
                      <span className="font-medium">{dp.title}</span>:{" "}
                      {dp.options.find((o) => o.key === dp.my_decision?.selected_option)?.label ?? dp.my_decision?.decision_text}{" "}
                      <span className="text-muted">({dp.my_decision?.confidence}% confidence)</span>
                    </li>
                  ))}
                </ul>
              )}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Operational map" description={state.map.name} icon={<MapIcon />} />
            <div className="p-2">
              <OpsMap
                locations={state.locations}
                reports={state.messages.map((m) => ({ location_key: m.location_key, title: m.title, at: m.received_sim_time }))}
                height={280}
              />
            </div>
          </Card>
        </div>

        <Card>
          <CardHeader
            title="Information feed"
            description="Only reports that have actually reached you"
            icon={<Inbox />}
            actions={<Badge tone="neutral">{state.messages.length}</Badge>}
          />
          <CardBody className="max-h-[calc(100vh-14rem)] overflow-y-auto">
            <InfoFeed messages={state.messages} simTime={sim} onAck={ended ? undefined : (id) => ack.mutate(id)} />
          </CardBody>
        </Card>

        <div className="space-y-4">
          <Card>
            <CardHeader title="Communications" icon={<Radio />} />
            <CardBody className="space-y-2">
              {state.channels.map((c) => (
                <ChannelRow key={c.id} channel={c} />
              ))}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Team communication" icon={<MessagesSquare />} />
            <TeamChat roomId={roomId} state={state} compact />
          </Card>
        </div>
      </div>
    </div>
  );
}
