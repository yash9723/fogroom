"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { InstructorState, TraineeState } from "@/lib/types";
import { qk, toastError } from "./rooms";

export function useInstructorState(roomId: string | undefined) {
  return useQuery({
    queryKey: qk.instructor(roomId ?? ""),
    queryFn: () => api<InstructorState>(`/rooms/${roomId}/state`),
    enabled: Boolean(roomId),
    refetchInterval: 15_000,
  });
}

export function useTraineeState(roomId: string | undefined) {
  return useQuery({
    queryKey: qk.trainee(roomId ?? ""),
    queryFn: () => api<TraineeState>(`/rooms/${roomId}/me`),
    enabled: Boolean(roomId),
    refetchInterval: 20_000,
  });
}

function useInstructorMutation<TVars>(roomId: string, fn: (vars: TVars) => Promise<unknown>, success?: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: fn,
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.instructor(roomId) });
      if (success) toast.success(success);
    },
    onError: (e) => toastError(e),
  });
}

export type ChannelPatch = { status?: string; reliability?: number; latency_ms?: number; restore?: boolean; reason?: string };

export function useChannelUpdate(roomId: string) {
  return useInstructorMutation(roomId, ({ channelId, patch }: { channelId: string; patch: ChannelPatch }) =>
    api(`/rooms/${roomId}/channels/${channelId}`, { method: "PATCH", body: patch }),
  );
}

export function useTriggerEvent(roomId: string) {
  return useInstructorMutation(
    roomId,
    (body: { template_key?: string; custom?: Record<string, unknown> }) => api(`/rooms/${roomId}/events/trigger`, { body }),
    "Event triggered",
  );
}

export function useSendNotice(roomId: string) {
  return useInstructorMutation(
    roomId,
    (body: { title?: string; content: string; channel_key?: string | null; target_participant_ids?: string[] }) =>
      api(`/rooms/${roomId}/notices`, { body }),
    "Notice sent",
  );
}

export function useInjectConflict(roomId: string) {
  return useInstructorMutation(
    roomId,
    (body: Record<string, unknown>) => api(`/rooms/${roomId}/conflicts`, { body }),
    "Conflicting report injected",
  );
}

export function useCreateDisruption(roomId: string) {
  return useInstructorMutation(
    roomId,
    (body: Record<string, unknown>) => api(`/rooms/${roomId}/disruptions`, { body }),
    "Disruption started",
  );
}

export function useEndDisruption(roomId: string) {
  return useInstructorMutation(
    roomId,
    (disruptionId: string) => api(`/rooms/${roomId}/disruptions/${disruptionId}/end`, { method: "POST" }),
    "Disruption ended",
  );
}

export function useOpenDecisionPoint(roomId: string) {
  return useInstructorMutation(
    roomId,
    (key: string) => api(`/rooms/${roomId}/decision-points/${key}/open`, { method: "POST" }),
    "Decision point opened",
  );
}

export function useAddNote(roomId: string) {
  return useInstructorMutation(
    roomId,
    (body: { content: string; participant_id?: string | null }) => api(`/rooms/${roomId}/notes`, { body }),
    "Note saved",
  );
}

export type DecisionSubmission = {
  selected_option: string | null;
  decision_text: string | null;
  rationale: string | null;
  confidence: number;
};

export function useSubmitDecision(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ key, body }: { key: string; body: DecisionSubmission }) =>
      api(`/rooms/${roomId}/decisions/${key}/submit`, { body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.trainee(roomId) });
      toast.success("Decision recorded");
    },
  });
}

export function useAcknowledge(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (deliveryId: string) => api(`/rooms/${roomId}/messages/${deliveryId}/ack`, { method: "POST" }),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.trainee(roomId) }),
    onError: (e) => toastError(e),
  });
}

export function useSendTeamMessage(roomId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { channel_key: string; message: string; recipient_participant_id?: string | null }) =>
      api<{ delivery_status: string; failure_reason: string | null }>(`/rooms/${roomId}/team-messages`, { body }),
    onSuccess: (res) => {
      qc.invalidateQueries({ queryKey: qk.trainee(roomId) });
      if (res.delivery_status === "FAILED") toast.warning(`Not delivered: ${res.failure_reason}`);
    },
    onError: (e) => toastError(e),
  });
}
