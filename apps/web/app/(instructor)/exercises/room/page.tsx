"use client";

import { ClipboardList } from "lucide-react";
import Link from "next/link";
import { WithQueryId } from "@/components/layout/with-query-id";
import { routes } from "@/lib/routes";
import { Lobby } from "@/components/instructor/lobby";
import { LiveConsole } from "@/components/instructor/live-console";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/feedback";
import { qk, useRoom } from "@/features/rooms";
import { useRoomSocket } from "@/hooks/use-room-socket";

export default function ExerciseRoomPage() {
  return <WithQueryId render={(id) => <ExerciseRoom key={id} roomId={id} />} />;
}

function ExerciseRoom({ roomId }: { roomId: string }) {
  const room = useRoom(roomId);
  useRoomSocket(roomId, { invalidate: [qk.room(roomId), qk.instructor(roomId)] });

  if (room.error) return <ErrorState message={room.error.message} />;
  if (room.isLoading || !room.data) return <LoadingBlock rows={6} />;

  const status = room.data.status;
  if (status === "LOBBY") return <Lobby room={room.data} />;
  if (status === "RUNNING" || status === "PAUSED") return <LiveConsole roomId={roomId} />;
  return (
    <Card className="mx-auto max-w-xl">
      <EmptyState
        icon={<ClipboardList />}
        title={`${room.data.name} has ended`}
        description="History is now immutable. Generate and open the After Action Review."
        action={
          <Button asChild variant="primary">
            <Link href={routes.aar(roomId)}>Open After Action Review</Link>
          </Button>
        }
      />
    </Card>
  );
}
