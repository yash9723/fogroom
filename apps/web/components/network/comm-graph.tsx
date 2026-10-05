"use client";

import type { ChannelStatus } from "@fogroom/shared";

export type GraphParticipant = { id: string; callsign: string; blackout: boolean; connected?: boolean };
export type GraphChannel = { id: string; key: string; name: string; status: ChannelStatus; health: number; fallback_channel_key: string | null };

const COLOR: Record<ChannelStatus, string> = { ONLINE: "#3fb87f", DEGRADED: "#e3a63c", OFFLINE: "#6f7a89" };
const DASH: Record<ChannelStatus, string | undefined> = { ONLINE: undefined, DEGRADED: "6 4", OFFLINE: "2 5" };

/**
 * 2D communication network: participants (left) linked to channels (right). Edge colour
 * AND dash pattern encode status (accessible without colour); a blacked-out participant's
 * links are all drawn as offline. Fallback routes are shown between channels.
 */
export function CommGraph({ participants, channels, height = 260 }: { participants: GraphParticipant[]; channels: GraphChannel[]; height?: number }) {
  const width = 520;
  const pad = 28;
  const py = (i: number, n: number) => pad + ((height - 2 * pad) * (i + 0.5)) / Math.max(n, 1);
  const pX = 90;
  const cX = width - 150;
  const chanY = new Map(channels.map((c, i) => [c.key, py(i, channels.length)]));

  return (
    <figure>
      <svg viewBox={`0 0 ${width} ${height}`} className="w-full" role="img" aria-label="Communication network graph">
        {participants.map((p, i) =>
          channels.map((c) => {
            const status: ChannelStatus = p.blackout ? "OFFLINE" : c.status;
            return (
              <line
                key={`${p.id}-${c.id}`}
                x1={pX + 34}
                y1={py(i, participants.length)}
                x2={cX - 8}
                y2={chanY.get(c.key)}
                stroke={COLOR[status]}
                strokeOpacity={status === "OFFLINE" ? 0.45 : 0.6}
                strokeWidth={status === "ONLINE" ? 1.6 : 1.2}
                strokeDasharray={DASH[status]}
              />
            );
          }),
        )}
        {channels
          .filter((c) => c.fallback_channel_key && chanY.has(c.fallback_channel_key))
          .map((c) => {
            const y1 = chanY.get(c.key) ?? 0;
            const y2 = chanY.get(c.fallback_channel_key as string) ?? 0;
            return (
              <path
                key={`fb-${c.key}`}
                d={`M ${cX + 112} ${y1} C ${cX + 140} ${y1}, ${cX + 140} ${y2}, ${cX + 112} ${y2}`}
                fill="none"
                stroke="#4fc1d6"
                strokeOpacity={0.35}
                strokeDasharray="3 3"
              />
            );
          })}
        {participants.map((p, i) => (
          <g key={p.id} transform={`translate(${pX}, ${py(i, participants.length)})`}>
            <circle r={16} fill="#141a23" stroke={p.blackout ? "#e5574e" : "#4fc1d6"} strokeWidth={1.5} />
            <text textAnchor="middle" dy="4" fontSize="9" fill="#e4eaf1" fontFamily="monospace">
              {p.callsign.slice(0, 3)}
            </text>
            <text x={-24} textAnchor="end" dy="4" fontSize="10" fill="#8b98a9">
              {p.callsign}
              {p.blackout ? " (blackout)" : ""}
            </text>
          </g>
        ))}
        {channels.map((c) => (
          <g key={c.id} transform={`translate(${cX}, ${chanY.get(c.key)})`}>
            <rect x={-8} y={-13} width={120} height={26} rx={5} fill="#141a23" stroke={COLOR[c.status]} strokeWidth={1.4} />
            <text x={2} dy="4" fontSize="10" fill="#e4eaf1">
              {c.name}
            </text>
            <text x={106} dy="4" textAnchor="end" fontSize="9" fill={COLOR[c.status]} fontFamily="monospace">
              {c.status === "OFFLINE" ? "OFF" : `${c.health}%`}
            </text>
          </g>
        ))}
      </svg>
      <figcaption className="mt-1 flex flex-wrap gap-3 px-1 text-[10px] text-muted">
        <span>━ online</span>
        <span>╍ degraded</span>
        <span>┈ offline / blackout</span>
        <span className="text-accent">⤷ fallback route</span>
      </figcaption>
    </figure>
  );
}
