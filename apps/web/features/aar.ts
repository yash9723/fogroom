"use client";

import type { RoomEvent } from "@fogroom/shared";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { ApiError, api, apiBlob } from "@/lib/api";
import type { AarEnvelope, DecisionInspection, ParticipantInfoState, TruthInfoState } from "@/lib/types";
import { qk, toastError } from "./rooms";

export function useAar(roomId: string | undefined) {
  return useQuery({
    queryKey: qk.aar(roomId ?? ""),
    queryFn: async () => {
      try {
        return await api<AarEnvelope>(`/rooms/${roomId}/aar`);
      } catch (e) {
        if (e instanceof ApiError && e.code === "AAR_NOT_FOUND") return null;
        throw e;
      }
    },
    enabled: Boolean(roomId),
  });
}

export function useGenerateAar(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api<AarEnvelope>(`/rooms/${roomId}/aar/generate`, { method: "POST" }),
    onSuccess: (data) => {
      qc.setQueryData(qk.aar(roomId), data);
      toast.success("After Action Review generated");
    },
    onError: (e) => toastError(e, "Could not generate AAR"),
  });
}

/** participantId === "truth" returns the global truth view. */
export function useInfoState(roomId: string, participantId: string, t: number, enabled = true) {
  const rounded = Math.round(t);
  return useQuery<TruthInfoState | ParticipantInfoState>({
    queryKey: qk.info(roomId, participantId, rounded),
    queryFn: (): Promise<TruthInfoState | ParticipantInfoState> =>
      participantId === "truth"
        ? api<TruthInfoState>(`/rooms/${roomId}/information-state/truth`, { query: { timestamp: rounded } })
        : api<ParticipantInfoState>(`/rooms/${roomId}/participants/${participantId}/information-state`, {
            query: { timestamp: rounded },
          }),
    enabled: enabled && Boolean(roomId && participantId),
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}

export function useInspection(roomId: string, decisionId: string | null) {
  return useQuery({
    queryKey: qk.inspection(roomId, decisionId ?? ""),
    queryFn: () => api<DecisionInspection>(`/rooms/${roomId}/decisions/${decisionId}/inspection`),
    enabled: Boolean(decisionId),
    staleTime: 60_000,
  });
}

export function useTimeline(roomId: string, filters: { event_type?: string[]; participant_id?: string; channel_key?: string }) {
  return useQuery({
    queryKey: qk.timeline(roomId, filters),
    queryFn: () =>
      api<{ events: RoomEvent[]; count: number }>(`/rooms/${roomId}/timeline`, {
        query: { event_type: filters.event_type, participant_id: filters.participant_id, channel_key: filters.channel_key },
      }),
    placeholderData: keepPreviousData,
  });
}

export function useRoomAnalytics(roomId: string) {
  return useQuery({
    queryKey: qk.roomAnalytics(roomId),
    queryFn: () =>
      api<{ series: Record<string, { sim_time: number; uncertainty_index: number; information_completeness: number; information_reliability: number; communication_health: number }[]> }>(
        `/rooms/${roomId}/analytics`,
      ),
  });
}

export async function downloadAarPdf(roomId: string, code: string) {
  try {
    const blob = await apiBlob(`/rooms/${roomId}/aar/export.pdf`);
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `FOGROOM-AAR-${code}.pdf`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2_000);
  } catch (e) {
    toastError(e, "Export failed");
  }
}
