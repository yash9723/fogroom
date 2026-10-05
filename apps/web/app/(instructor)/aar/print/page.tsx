"use client";

import { formatSimTime } from "@fogroom/shared";
import { Printer } from "lucide-react";
import { WithQueryId } from "@/components/layout/with-query-id";
import { Button } from "@/components/ui/button";
import { EmptyState, LoadingBlock } from "@/components/ui/feedback";
import { useAar } from "@/features/aar";

/** Print-optimised AAR (browser "Save as PDF" alternative to the server-generated PDF). */
export default function AarPrintPage() {
  return <WithQueryId render={(id) => <AarPrint key={id} roomId={id} />} />;
}

function AarPrint({ roomId }: { roomId: string }) {
  const aar = useAar(roomId);
  if (aar.isLoading) return <LoadingBlock rows={6} />;
  const env = aar.data;
  if (!env) return <EmptyState title="Generate the AAR first" />;
  const r = env.report;
  return (
    <div className="mx-auto max-w-4xl rounded-lg bg-white p-8 text-[13px] leading-relaxed text-neutral-900 print:p-0">
      <div className="no-print mb-4 flex justify-end">
        <Button variant="primary" onClick={() => window.print()}>
          <Printer aria-hidden /> Print / Save as PDF
        </Button>
      </div>
      <p className="text-xs uppercase tracking-widest text-neutral-500">FOGROOM · After Action Review</p>
      <h1 className="mt-1 text-2xl font-semibold">{r.exercise.title}</h1>
      <p className="text-neutral-600">
        {r.exercise.scenario} · Room {r.exercise.room_code} · Duration {r.exercise.duration_label} · {r.exercise.participant_count} participants
      </p>
      <p className="mt-4">{r.summary}</p>
      {env.narrative && <p className="mt-2 whitespace-pre-line text-neutral-700">{env.narrative}</p>}

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Objectives</h2>
      {r.objectives.map((o) => (
        <div key={o.key} className="mt-2">
          <strong>{o.title}</strong>
          <ul className="list-disc pl-5 text-neutral-700">
            {o.observations.map((x) => <li key={x}>{x}</li>)}
          </ul>
        </div>
      ))}

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Participant metrics</h2>
      <table className="mt-2 w-full border-collapse text-xs">
        <thead>
          <tr className="border-b border-neutral-400 text-left">
            {["Callsign", "Response", "Awareness", "Quality", "Coordination", "Uncertainty mgmt", "Avg conf.", "High-uncert."].map((h) => <th key={h} className="py-1">{h}</th>)}
          </tr>
        </thead>
        <tbody>
          {r.participants.map((p) => (
            <tr key={p.participant_id} className="border-b border-neutral-200">
              <td className="py-1 font-mono">{p.callsign}</td>
              <td>{p.decision_response_score.toFixed(0)}</td>
              <td>{p.information_awareness.toFixed(0)}</td>
              <td>{p.decision_quality.toFixed(0)}</td>
              <td>{p.coordination_score.toFixed(0)}</td>
              <td>{p.uncertainty_management.toFixed(0)}</td>
              <td>{p.average_confidence.toFixed(0)}%</td>
              <td>{p.decisions_under_high_uncertainty}</td>
            </tr>
          ))}
        </tbody>
      </table>

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Important decisions</h2>
      <ul className="mt-2 space-y-1">
        {r.decisions.map((d) => (
          <li key={d.id}>
            <span className="font-mono">{d.submitted_label}</span> <strong>{d.callsign}</strong> - {d.decision_point_title}:{" "}
            {d.selected_label ?? d.decision_text} ({d.confidence}% confidence, uncertainty {d.uncertainty_index?.toFixed(0)})
            {d.rationale && <em className="text-neutral-600"> - “{d.rationale}”</em>}
          </li>
        ))}
      </ul>

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Communication disruptions</h2>
      <ul className="mt-2 list-disc pl-5">
        {r.disruptions.map((d) => (
          <li key={d.id}>
            {formatSimTime(d.start_sim_time)}–{formatSimTime(d.end_sim_time)} {d.disruption_type} ({d.targets.join(", ")}
            {d.channels.length ? `; ${d.channels.join(", ")}` : ""})
          </li>
        ))}
      </ul>

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Timeline summary</h2>
      <ul className="mt-2 list-disc pl-5">
        {r.information_outcomes.filter((o) => o.narrative.length).map((o) => (
          <li key={o.label}>
            {formatSimTime(o.created_sim_time)} {o.title}: {o.narrative.join("; ")}
          </li>
        ))}
      </ul>

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Instructor notes</h2>
      <ul className="mt-2 list-disc pl-5">
        {r.notes.length ? r.notes.map((n, i) => <li key={i}>{n.label} {n.content}</li>) : <li>None recorded.</li>}
      </ul>

      <h2 className="mt-6 border-b border-neutral-300 pb-1 text-base font-semibold">Recommendations</h2>
      <ul className="mt-2 list-disc pl-5">
        {r.recommendations.map((x) => <li key={x}>{x}</li>)}
      </ul>
      <p className="mt-6 text-[11px] text-neutral-500">{r.metric_disclaimer} Fictional training exercise.</p>
    </div>
  );
}
