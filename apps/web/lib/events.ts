import type { RoomEvent } from "@fogroom/shared";
import {
  Activity,
  BellRing,
  CheckCircle2,
  CircleSlash,
  Clock,
  FastForward,
  Flag,
  GitBranch,
  Layers,
  type LucideIcon,
  MessageSquare,
  NotebookPen,
  Pause,
  Play,
  RadioTower,
  Send,
  ShieldAlert,
  Square,
  UserRound,
  Vote,
} from "lucide-react";

export type EventCategory =
  | "scenario"
  | "message"
  | "delivery"
  | "drop"
  | "delay"
  | "conflict"
  | "channel"
  | "disruption"
  | "decision"
  | "team"
  | "instructor"
  | "system";

export type Tone = "ok" | "warn" | "crit" | "off" | "accent" | "violet" | "info";

export type EventView = { title: string; detail?: string; tone: Tone; icon: LucideIcon; category: EventCategory };

const s = (v: unknown) => (v === null || v === undefined ? "" : String(v));

/** Human-readable, icon-coded description of a room event (instructor and trainee feeds). */
export function describeEvent(e: RoomEvent): EventView | null {
  const p = e.payload as Record<string, unknown>;
  switch (e.event_type) {
    case "simulation.started":
      return { title: "Exercise started", tone: "ok", icon: Play, category: "system" };
    case "simulation.paused":
      return { title: "Simulation paused", tone: "warn", icon: Pause, category: "system" };
    case "simulation.resumed":
      return { title: "Simulation resumed", tone: "ok", icon: Play, category: "system" };
    case "simulation.completed":
      return { title: "Exercise completed", detail: s(p.reason), tone: "off", icon: Square, category: "system" };
    case "clock.advanced":
      return { title: "Clock fast-forwarded", tone: "info", icon: FastForward, category: "instructor" };
    case "phase.changed":
      return { title: `Phase: ${s(p.name)}`, detail: s(p.description), tone: "accent", icon: Layers, category: "scenario" };
    case "scenario.event":
      return {
        title: `Scenario event: ${s(p.title)}`,
        detail: p.trigger_source === "INSTRUCTOR" ? "Triggered by instructor" : undefined,
        tone: "accent",
        icon: Flag,
        category: "scenario",
      };
    case "message.created":
      return { title: `${s(p.label)} created - ${s(p.title)}`, detail: s(p.content), tone: "info", icon: Send, category: "message" };
    case "message.delivered":
      return { title: `Report received: ${s(p.title)}`, detail: s(p.channel_name), tone: "ok", icon: CheckCircle2, category: "delivery" };
    case "delivery.completed": {
      const altered = p.status === "ALTERED";
      const delay = Number(p.delay_seconds ?? 0);
      return {
        title: `${s(p.label)} → ${s(p.callsign)}${altered ? " (altered version)" : ""}`,
        detail: delay >= 5 ? `Arrived ${delay.toFixed(0)}s after creation` : "Delivered on time",
        tone: altered ? "violet" : delay >= 5 ? "warn" : "ok",
        icon: altered ? GitBranch : CheckCircle2,
        category: altered ? "conflict" : "delivery",
      };
    }
    case "message.delayed":
      return {
        title: `${s(p.label)} delayed for ${s(p.callsign)}`,
        detail: `+${Number(p.delay_seconds ?? 0).toFixed(0)}s · ${(p.reasons as string[] | undefined)?.join("; ") ?? ""}`,
        tone: "warn",
        icon: Clock,
        category: "delay",
      };
    case "message.dropped":
      return {
        title: `${s(p.label)} dropped for ${s(p.callsign)}`,
        detail: (p.reasons as string[] | undefined)?.join("; "),
        tone: "crit",
        icon: CircleSlash,
        category: "drop",
      };
    case "message.held":
      return {
        title: `${s(p.label)} held${p.callsign ? ` for ${s(p.callsign)}` : ""}`,
        detail: (p.reasons as string[] | undefined)?.join("; "),
        tone: "warn",
        icon: Clock,
        category: "delay",
      };
    case "message.released":
      return { title: `${s(p.label)} released - path restored`, tone: "info", icon: RadioTower, category: "delay" };
    case "message.failed":
      return { title: `${s(p.label)} never delivered`, tone: "crit", icon: CircleSlash, category: "drop" };
    case "message.acknowledged":
      return { title: `${s(p.callsign)} acknowledged a report`, tone: "ok", icon: CheckCircle2, category: "team" };
    case "channel.updated":
      return {
        title: `${s(p.name)} → ${s(p.status)}`,
        detail: `${Math.round(Number(p.reliability ?? 0) * 100)}% reliability · ${s(p.reason)}`,
        tone: p.status === "ONLINE" ? "ok" : p.status === "DEGRADED" ? "warn" : "crit",
        icon: RadioTower,
        category: "channel",
      };
    case "comms.changed":
      return { title: "Your communications status changed", tone: "warn", icon: RadioTower, category: "channel" };
    case "disruption.started":
      return { title: `Disruption started: ${s(p.disruption_type).replaceAll("_", " ")}`, detail: s(p.source), tone: "crit", icon: ShieldAlert, category: "disruption" };
    case "disruption.ended":
      return { title: `Disruption ended: ${s(p.disruption_type).replaceAll("_", " ")}`, detail: s(p.reason), tone: "ok", icon: ShieldAlert, category: "disruption" };
    case "conflict.injected":
      return { title: `Conflicting report injected (${s(p.fact_key)} = ${s(p.fact_value)})`, tone: "violet", icon: GitBranch, category: "conflict" };
    case "decision.requested":
      return { title: `Decision requested: ${s(p.title)}`, tone: "accent", icon: Vote, category: "decision" };
    case "decision.submitted":
      return {
        title: `${s(p.callsign)} decided: ${s(p.selected_label ?? p.decision_text)}`,
        detail: `${s(p.decision_point_title)} · confidence ${s(p.confidence)}% · uncertainty ${Number(p.uncertainty_index ?? 0).toFixed(0)}`,
        tone: "accent",
        icon: Vote,
        category: "decision",
      };
    case "decision.acknowledged":
      return { title: "Your decision was recorded", tone: "ok", icon: Vote, category: "decision" };
    case "decision.closed":
      return { title: `Decision closed: ${s(p.title)}`, detail: s(p.reason), tone: "off", icon: Vote, category: "decision" };
    case "decision.missed":
      return { title: `Decision missed: ${s(p.key)}`, tone: "crit", icon: Vote, category: "decision" };
    case "team.message":
      return { title: `${s(p.sender_callsign)}: ${s(p.message)}`, detail: `via ${s(p.channel_key)}`, tone: "info", icon: MessageSquare, category: "team" };
    case "team.message_failed":
      return { title: `${s(p.sender_callsign)} message failed`, detail: s(p.failure_reason), tone: "crit", icon: MessageSquare, category: "team" };
    case "note.created":
      return { title: "Instructor note", detail: s(p.content), tone: "info", icon: NotebookPen, category: "instructor" };
    case "participant.joined":
      return { title: `${s(p.callsign)} joined`, detail: s(p.display_name), tone: "ok", icon: UserRound, category: "system" };
    case "participant.left":
      return { title: `${s(p.callsign)} removed`, tone: "off", icon: UserRound, category: "system" };
    case "participant.updated":
      return { title: `${s(p.callsign)} assigned role ${s(p.role)}`, tone: "info", icon: UserRound, category: "system" };
    case "participant.ready":
      return { title: `${s(p.callsign)} ${p.ready ? "is ready" : "not ready"}`, tone: "info", icon: UserRound, category: "system" };
    case "presence.updated":
      return { title: `${s(p.callsign)} ${p.status === "CONNECTED" ? "connected" : "disconnected"}`, tone: p.status === "CONNECTED" ? "ok" : "off", icon: Activity, category: "system" };
    case "room.created":
      return { title: `Room ${s(p.room_code)} created`, tone: "info", icon: BellRing, category: "system" };
    case "aar.generated":
      return { title: "AAR generated", tone: "info", icon: NotebookPen, category: "instructor" };
    default:
      return null;
  }
}

export const toneText: Record<Tone, string> = {
  ok: "text-ok",
  warn: "text-warn",
  crit: "text-crit",
  off: "text-muted",
  accent: "text-accent",
  violet: "text-violet",
  info: "text-info",
};
