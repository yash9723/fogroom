"use client";

import { PresenceBadge } from "@/components/status/indicators";
import { TeamChat } from "@/components/trainee/team-chat";
import { useTraineeRoomId } from "@/components/trainee/use-trainee-room";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useTraineeState } from "@/features/live";
import { qk } from "@/features/rooms";
import { useRoomSocket } from "@/hooks/use-room-socket";

export default function TeamPage() {
  const { roomId, loading } = useTraineeRoomId();
  const q = useTraineeState(roomId ?? undefined);
  useRoomSocket(roomId ?? undefined, { invalidate: [qk.trainee(roomId ?? "")] });
  if (loading || (roomId && !q.data)) return <LoadingBlock rows={5} />;
  if (!roomId || !q.data) return <EmptyState title="No active exercise" />;
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader eyebrow={q.data.room.scenario_name} title="Team communication" description="Messages travel over the selected channel and fail if it is offline." />
      <div className="grid gap-4 lg:grid-cols-[1fr_260px]">
        <Card>
          <TeamChat roomId={roomId} state={q.data} />
        </Card>
        <Card>
          <CardHeader title="Team" />
          <CardBody className="space-y-2">
            {q.data.teammates.map((t) => (
              <div key={t.id} className="flex items-center justify-between rounded-md border border-line bg-panel-2 px-3 py-2">
                <div>
                  <div className="font-mono text-sm text-accent">{t.callsign}</div>
                  <div className="text-[11px] text-muted">{t.role_name}</div>
                </div>
                <PresenceBadge status={t.connection_status} />
              </div>
            ))}
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
