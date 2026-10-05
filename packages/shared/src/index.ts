/**
 * Shared contracts between the FOGROOM API and web client.
 * The API mirrors these with Pydantic; the web client validates every
 * WebSocket frame with these zod schemas before using it.
 */
import { z } from "zod";

export const EVENT_TYPES = [
  "room.created",
  "participant.joined",
  "participant.left",
  "participant.updated",
  "participant.ready",
  "presence.updated",
  "simulation.started",
  "simulation.paused",
  "simulation.resumed",
  "simulation.completed",
  "clock.advanced",
  "phase.changed",
  "scenario.event",
  "message.created",
  "message.delivered",
  "delivery.completed",
  "message.delayed",
  "message.dropped",
  "message.held",
  "message.released",
  "message.failed",
  "message.acknowledged",
  "channel.updated",
  "comms.changed",
  "disruption.started",
  "disruption.ended",
  "conflict.injected",
  "decision.requested",
  "decision.submitted",
  "decision.acknowledged",
  "decision.closed",
  "decision.missed",
  "team.message",
  "team.message_failed",
  "note.created",
  "metrics.updated",
  "aar.generated",
] as const;

export type EventType = (typeof EVENT_TYPES)[number];

export const roomEventSchema = z.object({
  seq: z.number().int().nullable(),
  room_id: z.string().nullable().optional(),
  event_type: z.string(),
  sim_time: z.number().nullable(),
  timestamp: z.string().nullable(),
  visibility: z.enum(["ALL", "INSTRUCTOR", "PARTICIPANTS"]),
  targets: z.array(z.string()).optional(),
  actor_type: z.string().optional(),
  payload: z.record(z.string(), z.unknown()),
});
export type RoomEvent = z.infer<typeof roomEventSchema>;

export const helloFrameSchema = z.object({
  type: z.literal("hello"),
  room_id: z.string(),
  last_seq: z.number().int(),
  room_status: z.string(),
  viewer: z.enum(["INSTRUCTOR", "TRAINEE"]),
  participant_id: z.string().nullable(),
});

export const serverFrameSchema = z.discriminatedUnion("type", [
  helloFrameSchema,
  z.object({ type: z.literal("event"), event: roomEventSchema }),
  z.object({ type: z.literal("pong"), server_time: z.string() }),
  z.object({ type: z.literal("error"), code: z.string(), message: z.string() }),
]);
export type ServerFrame = z.infer<typeof serverFrameSchema>;

export type ChannelStatus = "ONLINE" | "DEGRADED" | "OFFLINE";
export type RoomStatus = "LOBBY" | "RUNNING" | "PAUSED" | "COMPLETED" | "ARCHIVED";
export type Role = "ADMIN" | "INSTRUCTOR" | "TRAINEE";
export type DeliveryStatus = "PENDING" | "DELIVERED" | "DELAYED" | "DROPPED" | "ALTERED" | "FAILED";
export type DisruptionType =
  | "DELAY"
  | "DROPOUT"
  | "CHANNEL_FAILURE"
  | "RELIABILITY_REDUCTION"
  | "CONFLICT_INJECTION"
  | "BLACKOUT";

export const apiErrorSchema = z.object({
  error: z.object({
    code: z.string(),
    message: z.string(),
    details: z.unknown().optional(),
  }),
});
export type ApiErrorBody = z.infer<typeof apiErrorSchema>;

/** Format simulation seconds as T+MM:SS. */
export function formatSimTime(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "T+--:--";
  const total = Math.max(0, Math.floor(seconds));
  const m = Math.floor(total / 60);
  const s = total % 60;
  return `T+${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}
