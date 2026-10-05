/** API response types (mirrors apps/api schemas / read models). */
import type { ChannelStatus, Role, RoomEvent, RoomStatus } from "@fogroom/shared";

export type User = {
  id: string;
  email: string;
  display_name: string;
  role: Role;
  avatar_url: string | null;
  is_active: boolean;
  created_at: string;
};

export type TokenPair = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  expires_in: number;
  user: User;
};

export type RoleDef = { key: string; name: string; callsign: string };

export type ParticipantSummary = {
  id: string;
  user_id: string;
  display_name: string;
  callsign: string;
  assigned_role: string | null;
  role_name: string | null;
  team: string | null;
  connection_status: "CONNECTED" | "DISCONNECTED";
  is_ready: boolean;
  joined_at: string | null;
  last_seen_at: string | null;
};

export type RoomSummary = {
  id: string;
  room_code: string;
  name: string;
  status: RoomStatus;
  scenario_id: string | null;
  scenario_name: string | null;
  scenario_description: string | null;
  difficulty: string | null;
  estimated_duration_minutes: number | null;
  instructor: { id: string; display_name: string } | null;
  time_scale: number;
  created_at: string | null;
  started_at: string | null;
  ended_at: string | null;
  sim_time: number;
  current_phase_key: string | null;
  roles: RoleDef[];
  participants: ParticipantSummary[];
};

export type Channel = {
  id: string;
  key: string;
  name: string;
  channel_type: string;
  status: ChannelStatus;
  base_status: ChannelStatus;
  reliability: number;
  latency_ms: number;
  health: number;
  weight: number;
  fallback_channel_key: string | null;
};

export type Phase = { key: string; name: string; description?: string; starts_at_seconds: number };

export type Location = { key: string; name: string; x: number; y: number; kind: string };

export type DecisionOption = { key: string; label: string; description?: string; truth_alignment?: number };

export type DecisionPoint = {
  id: string;
  key: string;
  title: string;
  prompt: string;
  options: DecisionOption[];
  allow_custom: boolean;
  require_rationale: boolean;
  status: "OPEN" | "CLOSED";
  opened_sim_time: number;
  deadline_sim_time: number | null;
  closed_sim_time: number | null;
  critical: boolean;
};

export type MyDecision = {
  id: string;
  selected_option: string | null;
  decision_text: string | null;
  rationale: string | null;
  confidence: number;
  submitted_sim_time: number;
  response_time_ms: number;
};

export type TraineeMessage = {
  id: string;
  title: string;
  content: string;
  source: string;
  reliability: "HIGH" | "MEDIUM" | "LOW";
  priority: "LOW" | "NORMAL" | "HIGH" | "CRITICAL";
  channel_key: string | null;
  channel_name: string;
  sender_type: string;
  location_key: string | null;
  report_sim_time: number;
  received_sim_time: number | null;
  acknowledged: boolean;
};

export type TeamMessage = {
  id: string;
  sender_participant_id: string;
  sender_callsign: string | null;
  recipient_participant_id: string | null;
  recipient_callsign: string | null;
  message: string;
  sim_time: number;
  delivery_status: string;
  failure_reason: string | null;
  channel_key: string | null;
};

export type TraineeState = {
  room: {
    id: string;
    room_code: string;
    name: string;
    status: RoomStatus;
    scenario_name: string;
    time_scale: number;
    sim_time: number;
    phase: Phase | null;
  };
  participant: {
    id: string;
    callsign: string;
    assigned_role: string | null;
    role_name: string | null;
    role_description: string | null;
    role_objectives: string[];
    team: string | null;
  };
  briefing: string;
  objectives: { key: string; title: string; description: string }[];
  locations: Location[];
  map: { name?: string; width?: number; height?: number };
  channels: Channel[];
  blackout: boolean;
  communication_health: number;
  messages: TraineeMessage[];
  decision_points: (DecisionPoint & { my_decision: MyDecision | null })[];
  teammates: { id: string; callsign: string; role_name: string | null; connection_status: string }[];
  team_messages: TeamMessage[];
  notices: RoomEvent[];
  last_seq: number;
};

export type InfoMetrics = {
  information_completeness: number;
  information_reliability: number;
  communication_health: number;
  known_contradictions: number;
  information_confidence: number;
  uncertainty_index: number;
  counts?: { received: number; pending: number; dropped: number; not_addressed: number };
};

export type InstructorParticipant = ParticipantSummary & {
  deliveries: { received: number; altered: number; in_flight: number; dropped: number; failed: number };
  metrics: InfoMetrics | null;
};

export type Disruption = {
  id: string;
  disruption_type: string;
  target_participant_ids: string[];
  target_channel_ids: string[];
  severity: number;
  configuration: Record<string, unknown>;
  start_sim_time: number;
  end_sim_time: number | null;
  planned_end_sim_time: number | null;
  is_active: boolean;
  source: string;
};

export type DecisionRow = {
  id: string;
  participant_id: string;
  callsign: string | null;
  decision_point_key: string | null;
  decision_point_title: string | null;
  selected_option: string | null;
  selected_label: string | null;
  decision_text: string | null;
  rationale: string | null;
  confidence: number;
  response_time_ms: number;
  submitted_sim_time: number;
};

export type TimelineItem = {
  kind: "EVENT" | "DECISION";
  key: string;
  title: string;
  event_type?: string;
  trigger_type: string;
  scheduled_sim_time: number | null;
  fired_sim_time: number | null;
  status: string;
  channel_key?: string | null;
  has_variants?: boolean;
};

export type VariantRef = {
  event_key: string;
  fact_key: string | null;
  canonical_value: string | null;
  variant_key: string;
  variant_value: string;
  content: string;
};

export type InstructorState = {
  room: RoomSummary;
  sim_time: number;
  phase: Phase | null;
  phases: Phase[];
  channels: Channel[];
  participants: InstructorParticipant[];
  disruptions: Disruption[];
  decision_points: (DecisionPoint & { target_participant_ids: string[]; submitted_participant_ids: string[] })[];
  decisions: DecisionRow[];
  timeline: TimelineItem[];
  events: RoomEvent[];
  notes: { id: string; sim_time: number; content: string; participant_id: string | null }[];
  variants: VariantRef[];
  facts: { key: string; label: string; timeline: { from_seconds: number; value: string }[] }[];
  locations: Location[];
  objectives: { key: string; title: string; description: string }[];
  last_seq: number;
};

export type InfoItem = {
  message_id: string;
  label: string;
  title: string;
  canonical_content: string;
  source: string;
  source_reliability: string;
  priority: string;
  importance_weight: number;
  channel_key: string | null;
  channel_name: string;
  fact_key: string | null;
  fact_value: string | null;
  location_key: string | null;
  created_sim_time: number;
  truth_value_at_t?: string | null;
  delivery_id?: string;
  status?: string;
  transformation_type?: string;
  reasons?: string[];
  delivered_title?: string | null;
  delivered_content?: string | null;
  delivered_fact_value?: string | null;
  delivered_source?: string | null;
  delivered_source_reliability?: string | null;
  reliability_score?: number;
  received_sim_time?: number | null;
  scheduled_sim_time?: number | null;
  delay_seconds?: number;
  acknowledged?: boolean;
  altered?: boolean;
  eventual_outcome?: "DELIVERED_LATER" | "NEVER_DELIVERED" | "IN_FLIGHT";
  arrives_sim_time?: number | null;
  deliveries?: { participant_id: string; callsign: string; state: string; received_sim_time: number | null; delivered_fact_value: string | null }[];
};

export type Contradiction = {
  fact_key: string;
  label: string;
  reports: { value: string; label: string; title: string; source: string; source_reliability: string; received_sim_time: number | null }[];
};

export type Belief = {
  fact_key: string;
  label: string;
  believed_value: string;
  based_on: string;
  truth_value: string | null;
  accurate: boolean;
};

export type InfoChannel = {
  id: string;
  key: string;
  name: string;
  channel_type: string;
  weight: number;
  status: ChannelStatus;
  base_status: ChannelStatus;
  reliability: number;
  latency_ms: number;
};

export type ParticipantInfoState = {
  view: "PARTICIPANT";
  room_id: string;
  sim_time: number;
  participant: { id: string; callsign: string; role: string | null };
  received: InfoItem[];
  pending: InfoItem[];
  dropped: InfoItem[];
  not_addressed: InfoItem[];
  channels: InfoChannel[];
  unavailable_channel_ids: string[];
  blackout: boolean;
  contradictions: Contradiction[];
  beliefs: Belief[];
  decisions: { id: string; decision_point_key: string | null; selected_option: string | null; confidence: number; submitted_sim_time: number }[];
  open_decision_points: { key: string; title: string }[];
  metrics: InfoMetrics;
  truth: { facts: { key: string; label: string; value: string | null }[] };
  active_disruptions: { id: string; disruption_type: string; target_participant_ids: string[]; target_channel_ids: string[] }[];
};

export type TruthInfoState = {
  view: "TRUTH";
  room_id: string;
  sim_time: number;
  participant: null;
  messages: InfoItem[];
  channels: InfoChannel[];
  participants: {
    participant_id: string;
    callsign: string;
    role: string | null;
    metrics: InfoMetrics;
    contradictions: number;
    inaccurate_beliefs: Belief[];
  }[];
  decisions: { id: string; participant_id: string; callsign: string; selected_option: string | null; confidence: number; submitted_sim_time: number }[];
  metrics: { communication_health: number; message_count: number; mean_uncertainty_index: number };
  truth: { facts: { key: string; label: string; value: string | null }[] };
  active_disruptions: { id: string; disruption_type: string; target_participant_ids: string[]; target_channel_ids: string[] }[];
};

export type AarDecision = {
  id: string;
  participant_id: string;
  callsign: string;
  decision_point_key: string;
  decision_point_title: string;
  critical: boolean;
  selected_option: string | null;
  selected_label: string | null;
  decision_type: string;
  decision_text: string | null;
  rationale: string | null;
  confidence: number;
  submitted_sim_time: number;
  submitted_label: string;
  response_time_ms: number;
  decision_quality: number;
  custom_needs_review: boolean;
  response_score: number;
  information_completeness: number | null;
  information_reliability: number | null;
  communication_health: number | null;
  known_contradictions: number;
  information_confidence: number;
  uncertainty_index: number | null;
  calibration: number;
  relevant_beliefs: Belief[];
  missing_relevant: { label: string; title: string; fact_key: string | null; state: string }[];
  contradictions: Contradiction[];
};

export type AarParticipant = {
  participant_id: string;
  callsign: string;
  display_name: string;
  role: string | null;
  decision_response_score: number;
  information_awareness: number;
  decision_quality: number;
  coordination_score: number;
  uncertainty_management: number;
  average_confidence: number;
  average_response_time_s: number;
  decisions_under_high_uncertainty: number;
  decisions_made: number;
  decisions_missed: string[];
  overall_score: number;
  contradictions_encountered: number;
  acknowledgement_rate: number;
  team_messages_sent: number;
  messages: {
    addressed: number;
    received: number;
    altered: number;
    delayed: number;
    dropped: number;
    never_delivered: number;
    average_delay_s: number;
  };
};

export type AarReport = {
  exercise: {
    room_id: string;
    room_code: string;
    title: string;
    scenario: string;
    scenario_description: string;
    difficulty: string;
    started_at: string | null;
    ended_at: string | null;
    duration_seconds: number;
    duration_label: string;
    objectives: { key: string; title: string; description: string }[];
    participant_count: number;
  };
  summary: string;
  team: {
    team_score: number;
    decision_agreement: number;
    average_confidence: number;
    average_response_time_s: number;
    average_uncertainty_at_decision: number;
    average_coordination: number;
    delivery_status_counts: Record<string, number>;
    messages_created: number;
    disruptions: number;
    team_messages: number;
  };
  participants: AarParticipant[];
  decisions: AarDecision[];
  critical_decisions: AarDecision[];
  disruptions: {
    id: string;
    disruption_type: string;
    source: string;
    severity: number;
    start_sim_time: number;
    end_sim_time: number | null;
    targets: string[];
    channels: string[];
    configuration: Record<string, unknown>;
  }[];
  channel_history: { channel: string; sim_time: number; status: ChannelStatus; reliability: number; latency_ms: number; reason: string }[];
  information_outcomes: {
    label: string;
    title: string;
    created_sim_time: number;
    fact_key: string | null;
    fact_value: string | null;
    importance_weight: number;
    outcomes: { callsign: string; status: string; delay_seconds: number; transformation_type: string; delivered_fact_value: string | null; reasons: string[] }[];
    narrative: string[];
  }[];
  objectives: { key: string; title: string; description: string; observations: string[] }[];
  recommendations: string[];
  notes: { sim_time: number; label: string; content: string; callsign: string | null }[];
  timeline_counts: Record<string, number>;
  formulas: Record<string, string>;
  metric_disclaimer: string;
};

export type AarEnvelope = {
  id: string;
  room_id: string;
  generated_at: string;
  version: number;
  summary: string;
  team_score: number;
  narrative: string | null;
  narrative_source: "AI" | "TEMPLATE";
  report: AarReport;
};

export type DecisionInspection = {
  decision: AarDecision;
  decision_point: {
    key: string;
    title: string;
    prompt: string;
    options: DecisionOption[];
    opened_sim_time: number;
    deadline_sim_time: number | null;
    relevant_fact_keys: string[];
  };
  participant: { id: string; callsign: string | null; role: string | null };
  snapshot_time: number;
  available_information: InfoItem[];
  missing_information: { dropped: InfoItem[]; not_addressed: InfoItem[]; in_flight: InfoItem[] };
  delayed_information: { arrived_late: InfoItem[]; arrived_after_decision: InfoItem[] };
  conflicting_information: Contradiction[];
  beliefs: Belief[];
  channels: InfoChannel[];
  metrics: InfoMetrics;
  truth: { facts: { key: string; label: string; value: string | null }[] };
};

export type ScenarioSummary = {
  id: string;
  name: string;
  description: string;
  difficulty: string;
  estimated_duration_minutes: number;
  category: string;
  role_count: number;
  channel_count: number;
  event_count: number;
  decision_count: number;
  created_at: string;
  updated_at: string;
};

export type DashboardData = {
  active: RoomBrief[];
  scheduled: RoomBrief[];
  completed: RoomBrief[];
  recent_reports: { room_id: string; room_name: string; generated_at: string; team_score: number; summary: string }[];
  average_team_score: number | null;
  recent_participants: { user_id: string; display_name: string; callsign: string; room_name: string; joined_at: string }[];
  counts: { total: number; active: number; completed: number; reports: number };
};

export type RoomBrief = {
  id: string;
  room_code: string;
  name: string;
  status: RoomStatus;
  scenario_name: string | null;
  created_at: string;
  started_at: string | null;
  ended_at: string | null;
};

export type AnalyticsOverview = {
  total_exercises: number;
  total_decisions: number;
  average_response_time_s: number;
  average_uncertainty_at_decision: number;
  average_coordination_score: number;
  average_team_score: number;
  reports_generated: number;
  confidence_distribution: { range: string; count: number }[];
  degradation_frequency: { type: string; count: number }[];
  delivery_outcomes: { status: string; count: number }[];
  participant_trends: { name: string; points: { room: string; order: number; date: string; overall_score: number; decision_quality: number; uncertainty_management: number }[] }[];
  exercises: { id: string; name: string; ended_at: string | null; team_score: number | null }[];
};
