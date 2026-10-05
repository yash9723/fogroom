"use client";

import { Card, CardBody } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { InfoFeed } from "@/components/trainee/info-feed";
import { useTraineeRoomId } from "@/components/trainee/use-trainee-room";
import { useAcknowledge, useTraineeState } from "@/features/live";

export default function MessagesPage() {
  const { roomId, loading } = useTraineeRoomId();
  const q = useTraineeState(roomId ?? undefined);
  const ack = useAcknowledge(roomId ?? "");
  if (loading || (roomId && !q.data)) return <LoadingBlock rows={5} />;
  if (!roomId || !q.data) return <EmptyState title="No active exercise" description="Join an exercise to receive reports." />;
  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow={q.data.room.scenario_name} title="Messages" description="All reports delivered to you, newest first." />
      <Card>
        <CardBody>
          <InfoFeed messages={q.data.messages} simTime={q.data.room.sim_time} onAck={(id) => ack.mutate(id)} />
        </CardBody>
      </Card>
    </div>
  );
}
