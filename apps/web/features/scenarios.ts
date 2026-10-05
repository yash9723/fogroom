"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { toast } from "sonner";
import { api } from "@/lib/api";
import type { ScenarioSummary } from "@/lib/types";
import { qk, toastError } from "./rooms";

/** Scenario definitions are edited as JSON-compatible objects mirroring ScenarioCreate. */
export type ScenarioDoc = {
  id?: string;
  name: string;
  description: string;
  difficulty: "BEGINNER" | "INTERMEDIATE" | "ADVANCED";
  estimated_duration_minutes: number;
  category: string;
  briefing: string;
  objectives: { key: string; title: string; description: string }[];
  initial_conditions: { facts: unknown[]; locations: unknown[]; map: Record<string, unknown> };
  degradation_rules: {
    delay_probability?: number | null;
    drop_probability?: number | null;
    conflict_probability?: number | null;
    jitter_seconds?: number | null;
    channel_loss_factor?: number | null;
  };
  roles: { key: string; name: string; callsign: string; team: string; description: string; objectives: string[] }[];
  channels: {
    key: string;
    name: string;
    channel_type: string;
    initial_status: "ONLINE" | "DEGRADED" | "OFFLINE";
    reliability: number;
    latency_ms: number;
    weight: number;
    fallback_channel_key: string | null;
  }[];
  phases: { key: string; name: string; description: string; starts_at_seconds: number }[];
  events: ScenarioEventDoc[];
  decision_points: ScenarioDecisionDoc[];
};

export type ScenarioEventDoc = {
  key: string;
  event_type: string;
  title: string;
  content: string;
  trigger_type: string;
  scheduled_offset_seconds: number | null;
  trigger_decision_key: string | null;
  phase_key: string | null;
  channel_key: string | null;
  priority: string;
  source: string;
  source_reliability: string;
  reliability: number;
  importance_weight: number;
  fact_key: string | null;
  fact_value: string | null;
  location_key: string | null;
  targeting_rules: { recipients: "all" | string[]; overrides: Record<string, { action: string; seconds?: number | null; variant?: string | null }>; degradation?: Record<string, number | null> | null };
  variants: { key: string; fact_value: string; title?: string | null; content: string; source?: string | null; source_reliability?: string | null }[];
  effects: Record<string, unknown> | null;
  metadata: Record<string, unknown>;
};

export type ScenarioDecisionDoc = {
  key: string;
  title: string;
  prompt: string;
  options: { key: string; label: string; description: string; truth_alignment: number }[];
  trigger_type: string;
  opens_at_seconds: number | null;
  trigger_decision_key: string | null;
  deadline_seconds: number;
  allow_custom: boolean;
  require_rationale: boolean;
  target_roles: string[];
  phase_key: string | null;
  critical: boolean;
  relevant_fact_keys: string[];
};

export function useScenarios() {
  return useQuery({ queryKey: qk.scenarios, queryFn: () => api<ScenarioSummary[]>("/scenarios") });
}

export function useScenario(id: string | undefined) {
  return useQuery({
    queryKey: qk.scenario(id ?? ""),
    queryFn: () => api<ScenarioDoc>(`/scenarios/${id}`),
    enabled: Boolean(id) && id !== "new",
  });
}

const STRIP = ["id", "created_at", "updated_at", "created_by", "is_published"] as const;

export function toScenarioPayload(doc: ScenarioDoc): Record<string, unknown> {
  const copy: Record<string, unknown> = { ...doc };
  STRIP.forEach((k) => delete copy[k]);
  return copy;
}

export function useSaveScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (doc: ScenarioDoc) =>
      doc.id
        ? api<ScenarioDoc>(`/scenarios/${doc.id}`, { method: "PUT", body: toScenarioPayload(doc) })
        : api<ScenarioDoc>("/scenarios", { body: toScenarioPayload(doc) }),
    onSuccess: (saved) => {
      qc.invalidateQueries({ queryKey: qk.scenarios });
      if (saved.id) qc.setQueryData(qk.scenario(saved.id), saved);
      toast.success("Scenario saved");
    },
    onError: (e) => toastError(e, "Scenario could not be saved"),
  });
}

export function useDuplicateScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api<ScenarioDoc>(`/scenarios/${id}/duplicate`, { method: "POST" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.scenarios });
      toast.success("Scenario duplicated");
    },
    onError: (e) => toastError(e),
  });
}

export function useDeleteScenario() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api(`/scenarios/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.scenarios });
      toast.success("Scenario deleted");
    },
    onError: (e) => toastError(e),
  });
}
