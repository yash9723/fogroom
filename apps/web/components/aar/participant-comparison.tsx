"use client";

import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { AarParticipant } from "@/lib/types";
import { cn, scoreTone } from "@/lib/utils";

const METRICS: { key: keyof AarParticipant; label: string }[] = [
  { key: "decision_response_score", label: "Decision response" },
  { key: "information_awareness", label: "Information awareness" },
  { key: "decision_quality", label: "Decision quality" },
  { key: "coordination_score", label: "Coordination" },
  { key: "uncertainty_management", label: "Uncertainty mgmt" },
];

const PALETTE = ["#4fc1d6", "#e3a63c", "#a48cf0", "#3fb87f", "#e5574e", "#7aa5f5"];

const tone = (v: number) => ({ ok: "text-ok", warn: "text-warn", crit: "text-crit", off: "text-muted" })[scoreTone(v)];

export function ParticipantComparison({ participants }: { participants: AarParticipant[] }) {
  const data = METRICS.map((m) => ({
    metric: m.label,
    ...Object.fromEntries(participants.map((p) => [p.callsign, Number(p[m.key])])),
  }));
  return (
    <div className="space-y-4">
      <div className="overflow-x-auto">
        <table className="w-full text-sm" aria-label="Participant comparison">
          <thead>
            <tr className="border-b border-line text-left text-xs text-muted">
              <th className="py-2 pr-3 font-medium">Metric</th>
              {participants.map((p) => (
                <th key={p.participant_id} className="px-3 py-2 font-mono font-medium text-accent">
                  {p.callsign}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {METRICS.map((m) => (
              <tr key={m.key}>
                <td className="py-1.5 pr-3 text-xs text-muted">{m.label}</td>
                {participants.map((p) => (
                  <td key={p.participant_id} className={cn("px-3 py-1.5 font-mono tabular", tone(Number(p[m.key])))}>
                    {Number(p[m.key]).toFixed(0)}
                  </td>
                ))}
              </tr>
            ))}
            <tr>
              <td className="py-1.5 pr-3 text-xs text-muted">Average confidence</td>
              {participants.map((p) => (
                <td key={p.participant_id} className="px-3 py-1.5 font-mono tabular">{p.average_confidence.toFixed(0)}%</td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-xs text-muted">Decisions under high uncertainty</td>
              {participants.map((p) => (
                <td key={p.participant_id} className="px-3 py-1.5 font-mono tabular">{p.decisions_under_high_uncertainty}</td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-xs text-muted">Reports received / dropped / delayed / altered</td>
              {participants.map((p) => (
                <td key={p.participant_id} className="px-3 py-1.5 font-mono text-xs tabular">
                  {p.messages.received} / <span className="text-crit">{p.messages.dropped}</span> /{" "}
                  <span className="text-warn">{p.messages.delayed}</span> / <span className="text-violet">{p.messages.altered}</span>
                </td>
              ))}
            </tr>
            <tr>
              <td className="py-1.5 pr-3 text-xs font-semibold">Overall (experimental)</td>
              {participants.map((p) => (
                <td key={p.participant_id} className={cn("px-3 py-1.5 font-mono font-semibold tabular", tone(p.overall_score))}>
                  {p.overall_score.toFixed(0)}
                </td>
              ))}
            </tr>
          </tbody>
        </table>
      </div>
      <div className="h-64" aria-label="Participant comparison chart" role="img">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} margin={{ top: 8, right: 8, bottom: 8, left: -16 }}>
            <CartesianGrid stroke="#222b37" vertical={false} />
            <XAxis dataKey="metric" tick={{ fill: "#8b98a9", fontSize: 11 }} />
            <YAxis domain={[0, 100]} tick={{ fill: "#8b98a9", fontSize: 11 }} />
            <Tooltip contentStyle={{ background: "#141a23", border: "1px solid #2e3a4a", fontSize: 12 }} />
            <Legend wrapperStyle={{ fontSize: 12 }} />
            {participants.map((p, i) => (
              <Bar key={p.participant_id} dataKey={p.callsign} fill={PALETTE[i % PALETTE.length]} radius={[3, 3, 0, 0]} />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
