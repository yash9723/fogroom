"use client";

import { routes } from "@/lib/routes";
import { PlayCircle } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RoomStatusBadge } from "@/components/status/indicators";
import { JoinForm } from "@/components/trainee/join-form";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useJoinRoom, useRooms } from "@/features/rooms";

export default function TraineeHome() {
  const router = useRouter();
  const rooms = useRooms();
  const join = useJoinRoom();

  return (
    <div className="mx-auto max-w-3xl">
      <PageHeader eyebrow="Trainee" title="Active exercise" description="Join with the room code from your instructor." />
      <Card className="mb-6">
        <CardBody>
          <JoinForm
            onJoin={async (code) => {
              const res = await join.mutateAsync(code);
              router.push(routes.traineeExercise(res.room.id));
            }}
          />
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="My exercises" icon={<PlayCircle />} />
        {rooms.isLoading ? (
          <LoadingBlock className="p-4" />
        ) : !rooms.data?.length ? (
          <EmptyState title="You have not joined an exercise yet" />
        ) : (
          <ul className="divide-y divide-line">
            {rooms.data.map((r) => (
              <li key={r.id}>
                <Link href={routes.traineeExercise(r.id)} className="flex items-center justify-between px-4 py-3 hover:bg-panel-2">
                  <div>
                    <div className="text-sm font-medium">{r.name}</div>
                    <div className="text-xs text-muted">
                      <span className="font-mono">{r.room_code}</span> · {r.scenario_name}
                    </div>
                  </div>
                  <RoomStatusBadge status={r.status} />
                </Link>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}
