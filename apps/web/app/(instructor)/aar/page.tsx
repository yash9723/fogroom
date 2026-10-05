"use client";

import { ClipboardList } from "lucide-react";
import Link from "next/link";
import { RoomStatusBadge } from "@/components/status/indicators";
import { Card } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useRooms } from "@/features/rooms";
import { relativeTime } from "@/lib/utils";

export default function AarListPage() {
  const rooms = useRooms();
  const done = rooms.data?.filter((r) => r.status === "COMPLETED" || r.status === "ARCHIVED") ?? [];
  return (
    <div className="mx-auto max-w-5xl">
      <PageHeader
        eyebrow="Instructor"
        title="After Action Reviews"
        description="Replay what each participant knew, inspect decisions and export reports."
      />
      {rooms.isLoading ? (
        <LoadingBlock rows={4} />
      ) : !done.length ? (
        <Card>
          <EmptyState icon={<ClipboardList />} title="No completed exercises" description="End a running exercise to review it here." />
        </Card>
      ) : (
        <Card className="divide-y divide-line">
          {done.map((r) => (
            <Link key={r.id} href={`/aar/${r.id}`} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-panel-2">
              <div>
                <div className="text-sm font-medium">{r.name}</div>
                <div className="text-xs text-muted">
                  <span className="font-mono">{r.room_code}</span> · {r.scenario_name} · {r.participants.length} participants · ended{" "}
                  {relativeTime(r.ended_at)}
                </div>
              </div>
              <RoomStatusBadge status={r.status} />
            </Link>
          ))}
        </Card>
      )}
    </div>
  );
}
