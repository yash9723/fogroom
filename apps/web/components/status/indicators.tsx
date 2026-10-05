"use client";

import type { ChannelStatus, RoomStatus } from "@fogroom/shared";
import {
  AlertTriangle,
  CheckCircle2,
  CircleDashed,
  CircleSlash,
  Clock,
  GitBranch,
  Radio,
  RadioTower,
  ShieldAlert,
  ShieldCheck,
  ShieldQuestion,
  Signal,
  SignalLow,
  WifiOff,
  Zap,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import type { Channel } from "@/lib/types";
import { useConnectionStore } from "@/lib/ui-store";
import { cn } from "@/lib/utils";

export function ChannelStatusBadge({ status }: { status: ChannelStatus }) {
  if (status === "ONLINE")
    return (
      <Badge tone="ok">
        <Signal aria-hidden /> Online
      </Badge>
    );
  if (status === "DEGRADED")
    return (
      <Badge tone="warn">
        <SignalLow aria-hidden /> Degraded
      </Badge>
    );
  return (
    <Badge tone="off">
      <WifiOff aria-hidden /> Offline
    </Badge>
  );
}

export function ChannelRow({ channel, dense = false }: { channel: Channel; dense?: boolean }) {
  const tone = channel.status === "ONLINE" ? "bg-ok" : channel.status === "DEGRADED" ? "bg-warn" : "bg-off";
  return (
    <div className={cn("rounded-md border border-line bg-panel-2", dense ? "px-2.5 py-2" : "px-3 py-2.5")}>
      <div className="flex items-center justify-between gap-2">
        <div className="flex min-w-0 items-center gap-2">
          <RadioTower className="size-3.5 shrink-0 text-subtle" aria-hidden />
          <span className="truncate text-xs font-semibold uppercase tracking-wide">{channel.name}</span>
        </div>
        <ChannelStatusBadge status={channel.status} />
      </div>
      <div className="mt-2 flex items-center gap-2">
        <div className="h-1 flex-1 overflow-hidden rounded-full bg-panel-3" aria-hidden>
          <div className={cn("h-full", tone)} style={{ width: `${channel.health}%` }} />
        </div>
        <span className="w-10 text-right font-mono text-xs tabular" aria-label={`${channel.name} health`}>
          {channel.health}%
        </span>
      </div>
      {!dense && (
        <div className="mt-1 text-[11px] text-subtle">
          Latency {(channel.latency_ms / 1000).toFixed(1)}s
          {channel.fallback_channel_key ? ` · fallback ${channel.fallback_channel_key}` : ""}
        </div>
      )}
    </div>
  );
}

export function ConnectionIndicator({ roomId }: { roomId: string }) {
  const status = useConnectionStore((s) => s.status[roomId] ?? "idle");
  const map = {
    open: { tone: "ok" as const, label: "Live", icon: <Radio aria-hidden /> },
    connecting: { tone: "warn" as const, label: "Connecting", icon: <CircleDashed aria-hidden /> },
    reconnecting: { tone: "warn" as const, label: "Reconnecting", icon: <CircleDashed aria-hidden /> },
    idle: { tone: "off" as const, label: "Idle", icon: <CircleDashed aria-hidden /> },
    closed: { tone: "off" as const, label: "Disconnected", icon: <WifiOff aria-hidden /> },
    unauthorized: { tone: "crit" as const, label: "Auth error", icon: <ShieldAlert aria-hidden /> },
  }[status];
  return (
    <Badge tone={map.tone} aria-live="polite" data-testid="connection-indicator">
      {map.icon}
      {map.label}
    </Badge>
  );
}

export function PresenceBadge({ status }: { status: string }) {
  return status === "CONNECTED" ? (
    <Badge tone="ok">
      <CheckCircle2 aria-hidden /> Connected
    </Badge>
  ) : (
    <Badge tone="off">
      <CircleSlash aria-hidden /> Offline
    </Badge>
  );
}

export function PriorityBadge({ priority }: { priority: string }) {
  const tone = priority === "CRITICAL" ? "crit" : priority === "HIGH" ? "warn" : priority === "LOW" ? "off" : "neutral";
  return (
    <Badge tone={tone}>
      {priority === "CRITICAL" && <Zap aria-hidden />}
      {priority}
    </Badge>
  );
}

export function ReliabilityBadge({ reliability }: { reliability: string }) {
  if (reliability === "HIGH")
    return (
      <Badge tone="ok" title="Reported source reliability">
        <ShieldCheck aria-hidden /> Reliability high
      </Badge>
    );
  if (reliability === "MEDIUM")
    return (
      <Badge tone="warn" title="Reported source reliability">
        <ShieldQuestion aria-hidden /> Reliability medium
      </Badge>
    );
  return (
    <Badge tone="crit" title="Reported source reliability">
      <ShieldAlert aria-hidden /> Reliability low
    </Badge>
  );
}

export function RoomStatusBadge({ status }: { status: RoomStatus | string }) {
  const tone =
    status === "RUNNING" ? "ok" : status === "PAUSED" ? "warn" : status === "LOBBY" ? "accent" : "off";
  return <Badge tone={tone}>{status}</Badge>;
}

export function DeliveryStateBadge({ state }: { state: string }) {
  const conf: Record<string, { tone: "ok" | "warn" | "crit" | "off" | "violet" | "info"; label: string; icon: React.ReactNode }> = {
    RECEIVED: { tone: "ok", label: "Received", icon: <CheckCircle2 aria-hidden /> },
    DELIVERED: { tone: "ok", label: "Delivered", icon: <CheckCircle2 aria-hidden /> },
    ALTERED: { tone: "violet", label: "Altered", icon: <GitBranch aria-hidden /> },
    DELAYED: { tone: "warn", label: "Delayed", icon: <Clock aria-hidden /> },
    IN_FLIGHT: { tone: "warn", label: "In flight", icon: <Clock aria-hidden /> },
    DELIVERED_LATER: { tone: "warn", label: "Arrives later", icon: <Clock aria-hidden /> },
    DROPPED: { tone: "crit", label: "Dropped", icon: <CircleSlash aria-hidden /> },
    FAILED: { tone: "crit", label: "Never delivered", icon: <AlertTriangle aria-hidden /> },
    NEVER_DELIVERED: { tone: "crit", label: "Never delivered", icon: <AlertTriangle aria-hidden /> },
    NOT_ADDRESSED: { tone: "off", label: "Not addressed", icon: <CircleDashed aria-hidden /> },
  };
  const c = conf[state] ?? { tone: "off" as const, label: state, icon: null };
  return (
    <Badge tone={c.tone}>
      {c.icon}
      {c.label}
    </Badge>
  );
}
