"use client";

import { useRooms } from "@/features/rooms";
import { useUiStore } from "@/lib/ui-store";

/** The trainee's current exercise: last opened room, else the most recent active one. */
export function useTraineeRoomId(): { roomId: string | null; loading: boolean } {
  const active = useUiStore((s) => s.activeRoomId);
  const rooms = useRooms();
  if (active) return { roomId: active, loading: false };
  const running = rooms.data?.find((r) => r.status === "RUNNING" || r.status === "PAUSED") ?? rooms.data?.[0];
  return { roomId: running?.id ?? null, loading: rooms.isLoading };
}
