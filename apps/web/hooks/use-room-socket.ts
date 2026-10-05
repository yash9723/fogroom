"use client";

import type { RoomEvent } from "@fogroom/shared";
import { useQueryClient, type QueryKey } from "@tanstack/react-query";
import { useEffect, useRef } from "react";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { useConnectionStore } from "@/lib/ui-store";
import { RoomSocket } from "@/lib/ws";

type Options = {
  /** Query keys refreshed (debounced) whenever an event arrives. */
  invalidate: QueryKey[];
  onEvent?: (event: RoomEvent) => void;
};

/**
 * Subscribes to a room's event stream. Server state stays in TanStack Query - events
 * trigger targeted refetches; on (re)connect we replay missed events from `/sync` so
 * nothing is lost across brief disconnects.
 */
export function useRoomSocket(roomId: string | undefined, { invalidate, onEvent }: Options) {
  const queryClient = useQueryClient();
  const setStatus = useConnectionStore((s) => s.setStatus);
  const lastSeq = useRef(0);
  const onEventRef = useRef(onEvent);
  const keysRef = useRef(invalidate);

  useEffect(() => {
    onEventRef.current = onEvent;
    keysRef.current = invalidate;
  });

  useEffect(() => {
    if (!roomId) return;
    let timer: ReturnType<typeof setTimeout> | null = null;
    const refresh = () => {
      if (timer) clearTimeout(timer);
      timer = setTimeout(() => {
        keysRef.current.forEach((key) => queryClient.invalidateQueries({ queryKey: key }));
      }, 120);
    };
    const handle = (event: RoomEvent) => {
      if (event.seq !== null && event.seq <= lastSeq.current) return;
      if (event.seq !== null) lastSeq.current = event.seq;
      onEventRef.current?.(event);
      refresh();
    };
    const socket = new RoomSocket(roomId, () => useAuthStore.getState().accessToken, {
      onStatus: (status) => setStatus(roomId, status),
      onEvent: handle,
      onHello: async (serverSeq) => {
        if (lastSeq.current > 0 && serverSeq > lastSeq.current) {
          try {
            const missed = await api<{ events: RoomEvent[] }>(`/rooms/${roomId}/sync`, {
              query: { since_seq: lastSeq.current },
            });
            missed.events.forEach(handle);
          } catch {
            /* full refetch below still rebuilds state */
          }
        }
        if (lastSeq.current === 0) lastSeq.current = serverSeq;
        refresh();
      },
    });
    socket.connect();
    return () => {
      if (timer) clearTimeout(timer);
      socket.close();
    };
  }, [roomId, queryClient, setStatus]);
}
