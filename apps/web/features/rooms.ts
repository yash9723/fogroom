"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError, api } from "@/lib/api";
import type { RoomSummary } from "@/lib/types";

export const qk = {
  me: ["me"] as const,
  rooms: ["rooms"] as const,
  room: (id: string) => ["room", id] as const,
  trainee: (id: string) => ["trainee-state", id] as const,
  instructor: (id: string) => ["instructor-state", id] as const,
  scenarios: ["scenarios"] as const,
  scenario: (id: string) => ["scenario", id] as const,
  aar: (id: string) => ["aar", id] as const,
  info: (id: string, pid: string, t: number) => ["info-state", id, pid, t] as const,
  inspection: (id: string, did: string) => ["inspection", id, did] as const,
  timeline: (id: string, filters: Record<string, unknown>) => ["timeline", id, filters] as const,
  dashboard: ["dashboard"] as const,
  overview: ["analytics-overview"] as const,
  roomAnalytics: (id: string) => ["room-analytics", id] as const,
};

export function toastError(error: unknown, fallback = "Action failed") {
  toast.error(error instanceof ApiError ? error.message : fallback, {
    description: error instanceof ApiError && error.code !== "NETWORK_ERROR" ? error.code : undefined,
  });
}

export function useRooms() {
  return useQuery({ queryKey: qk.rooms, queryFn: () => api<RoomSummary[]>("/rooms") });
}

export function useRoom(roomId: string | undefined) {
  return useQuery({
    queryKey: qk.room(roomId ?? ""),
    queryFn: () => api<RoomSummary>(`/rooms/${roomId}`),
    enabled: Boolean(roomId),
  });
}

export function useCreateRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { scenario_id: string; name?: string; time_scale?: number }) =>
      api<RoomSummary>("/rooms", { body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.rooms });
      qc.invalidateQueries({ queryKey: qk.dashboard });
    },
    onError: (e) => toastError(e, "Could not create room"),
  });
}

export function useLaunchDemo() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (timeScale: number) => api<RoomSummary>("/demo/launch", { body: { time_scale: timeScale } }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.rooms });
      qc.invalidateQueries({ queryKey: qk.dashboard });
    },
    onError: (e) => toastError(e, "Could not launch demo"),
  });
}

export async function joinRoomByCode(code: string) {
  return api<{ room: RoomSummary; participant_id: string; created: boolean }>("/rooms/join", {
    body: { room_code: code },
  });
}

export function useJoinRoom() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: joinRoomByCode,
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.rooms }),
  });
}

export type LifecycleAction = "start" | "pause" | "resume" | "end";

export function useLifecycle(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (action: LifecycleAction) => api<RoomSummary>(`/rooms/${roomId}/${action}`, { method: "POST" }),
    onSuccess: (room, action) => {
      qc.setQueryData(qk.room(roomId), room);
      qc.invalidateQueries({ queryKey: qk.instructor(roomId) });
      qc.invalidateQueries({ queryKey: qk.dashboard });
      const verb = { start: "Exercise started", pause: "Simulation paused", resume: "Simulation resumed", end: "Exercise ended" }[action];
      toast.success(verb);
    },
    onError: (e) => toastError(e),
  });
}

export function useAdvanceClock(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (to: number) => api<RoomSummary>(`/rooms/${roomId}/clock/advance`, { body: { to_sim_seconds: to } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.instructor(roomId) }),
    onError: (e) => toastError(e),
  });
}

export function useUpdateParticipant(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ participantId, role_key }: { participantId: string; role_key: string }) =>
      api<RoomSummary>(`/rooms/${roomId}/participants/${participantId}`, { method: "PATCH", body: { role_key } }),
    onSuccess: (room) => qc.setQueryData(qk.room(roomId), room),
    onError: (e) => toastError(e),
  });
}

export function useRemoveParticipant(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (participantId: string) =>
      api<RoomSummary>(`/rooms/${roomId}/participants/${participantId}`, { method: "DELETE" }),
    onSuccess: (room) => qc.setQueryData(qk.room(roomId), room),
    onError: (e) => toastError(e),
  });
}

export function useSetReady(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (ready: boolean) => api<RoomSummary>(`/rooms/${roomId}/ready`, { body: { ready } }),
    onSuccess: (room) => qc.setQueryData(qk.room(roomId), room),
    onError: (e) => toastError(e),
  });
}
