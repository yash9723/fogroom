"use client";

import { formatSimTime } from "@fogroom/shared";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { CommGraph } from "@/components/network/comm-graph";
import { ChannelStatusBadge, DeliveryStateBadge } from "@/components/status/indicators";
import { LoadingBlock } from "@/components/ui/feedback";
import { useRoomAnalytics } from "@/features/aar";
import type { AarReport } from "@/lib/types";

const PALETTE = ["#4fc1d6", "#e3a63c", "#a48cf0", "#3fb87f", "#e5574e"];

/** Gantt-style disruption timeline across the exercise duration. */
export function DisruptionTimeline({ report }: { report: AarReport }) {
  const duration = Math.max(1, report.exercise.duration_seconds);
  const rows = report.disruptions;
  if (!rows.length) return <p className="text-xs text-muted">No disruptions were applied.</p>;
  return (
    <div className="space-y-1.5" aria-label="Communication disruption timeline">
      {rows.map((d) => {
        const left = (d.start_sim_time / duration) * 100;
        const width = (((d.end_sim_time ?? duration) - d.start_sim_time) / duration) * 100;
        return (
          <div key={d.id} className="grid grid-cols-[180px_1fr] items-center gap-3 text-xs">
            <div className="truncate">
              <span className="font-medium">{d.disruption_type.replaceAll("_", " ")}</span>
              <span className="block text-[10px] text-muted">
                {d.targets.join(", ")} {d.channels.length ? `· ${d.channels.join(", ")}` : ""}
              </span>
            </div>
            <div className="relative h-4 rounded bg-panel-3">
              <div
                className="absolute h-4 rounded bg-crit/60"
                style={{ left: `${left}%`, width: `${Math.max(width, 0.8)}%` }}
                title={`${formatSimTime(d.start_sim_time)} → ${formatSimTime(d.end_sim_time ?? duration)}`}
              />
            </div>
          </div>
        );
      })}
      <div className="grid grid-cols-[180px_1fr] gap-3 font-mono text-[10px] text-subtle">
        <span />
        <div className="flex justify-between">
          <span>T+00:00</span>
          <span>{formatSimTime(duration)}</span>
        </div>
      </div>
    </div>
  );
}

export function UncertaintyChart({ roomId }: { roomId: string }) {
  const q = useRoomAnalytics(roomId);
  if (q.isLoading || !q.data) return <LoadingBlock rows={3} />;
  const keys = Object.keys(q.data.series).filter((k) => k !== "TEAM");
  const times = Array.from(new Set(Object.values(q.data.series).flatMap((s) => s.map((p) => Math.round(p.sim_time))))).sort((a, b) => a - b);
  const data = times.map((t) => ({
    t,
    label: formatSimTime(t),
    ...Object.fromEntries(keys.map((k) => [k, q.data.series[k].find((p) => Math.round(p.sim_time) === t)?.uncertainty_index])),
  }));
  return (
    <div className="h-64" role="img" aria-label="Uncertainty index over time per participant">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, bottom: 4, left: -16 }}>
          <CartesianGrid stroke="#222b37" vertical={false} />
          <XAxis dataKey="label" tick={{ fill: "#8b98a9", fontSize: 10 }} minTickGap={24} />
          <YAxis domain={[0, 100]} tick={{ fill: "#8b98a9", fontSize: 10 }} />
          <Tooltip contentStyle={{ background: "#141a23", border: "1px solid #2e3a4a", fontSize: 12 }} />
          <Legend wrapperStyle={{ fontSize: 12 }} />
          {keys.map((k, i) => (
            <Line key={k} type="monotone" dataKey={k} stroke={PALETTE[i % PALETTE.length]} dot={false} strokeWidth={2} connectNulls />
          ))}
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function CommsAnalysis({ roomId, report }: { roomId: string; report: AarReport }) {
  const channelNames = Array.from(new Set(report.channel_history.map((c) => c.channel)));
  const finalStatus = channelNames.map((name, i) => {
    const last = [...report.channel_history].reverse().find((c) => c.channel === name);
    return {
      id: `${i}`,
      key: name,
      name,
      status: last?.status ?? "ONLINE",
      health: last ? Math.round(last.reliability * 100) : 100,
      fallback_channel_key: null,
    };
  });
  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide">Uncertainty index over time</h3>
          <UncertaintyChart roomId={roomId} />
        </section>
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide">Communication graph (end state)</h3>
          <CommGraph participants={report.participants.map((p) => ({ id: p.participant_id, callsign: p.callsign, blackout: false }))} channels={finalStatus} />
        </section>
      </div>
      <section>
        <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide">Communication disruption timeline</h3>
        <DisruptionTimeline report={report} />
      </section>
      <div className="grid gap-6 lg:grid-cols-2">
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide">Channel history</h3>
          <ul className="max-h-72 space-y-1 overflow-y-auto text-xs">
            {report.channel_history.map((c, i) => (
              <li key={i} className="flex items-center gap-2">
                <span className="w-14 font-mono text-subtle">{formatSimTime(c.sim_time)}</span>
                <span className="w-28 truncate">{c.channel}</span>
                <ChannelStatusBadge status={c.status} />
                <span className="truncate text-muted">{c.reason}</span>
              </li>
            ))}
          </ul>
        </section>
        <section>
          <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide">What happened to each report</h3>
          <ul className="max-h-72 space-y-2 overflow-y-auto text-xs" data-testid="information-outcomes">
            {report.information_outcomes.map((o) => (
              <li key={o.label} className="rounded border border-line bg-panel-2 px-2.5 py-1.5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-subtle">{o.label}</span>
                  <span className="font-medium">{o.title}</span>
                </div>
                <div className="mt-1 flex flex-wrap gap-1">
                  {o.outcomes.map((x) => (
                    <span key={x.callsign} className="flex items-center gap-1">
                      <span className="font-mono text-[10px]">{x.callsign}</span>
                      <DeliveryStateBadge state={x.status} />
                    </span>
                  ))}
                </div>
                {o.narrative.length > 0 && <p className="mt-1 text-[11px] text-muted">{o.narrative.join("; ")}.</p>}
              </li>
            ))}
          </ul>
        </section>
      </div>
    </div>
  );
}
