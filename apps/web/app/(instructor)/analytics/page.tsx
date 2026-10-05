"use client";

import { BarChart3, Clock, Gauge, Users } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useAnalyticsOverview } from "@/features/analytics";
import { scoreTone, uncertaintyTone } from "@/lib/utils";

const PALETTE = ["#4fc1d6", "#e3a63c", "#a48cf0", "#3fb87f", "#e5574e", "#7aa5f5"];
const tooltip = { contentStyle: { background: "#141a23", border: "1px solid #2e3a4a", fontSize: 12 } };
const axis = { tick: { fill: "#8b98a9", fontSize: 11 } };

export default function AnalyticsPage() {
  const q = useAnalyticsOverview();
  const d = q.data;
  const trendRooms = Array.from(new Set(d?.participant_trends.flatMap((t) => t.points.map((p) => p.room)) ?? []));
  const trendData = trendRooms.map((room) => ({
    room,
    ...Object.fromEntries((d?.participant_trends ?? []).map((t) => [t.name, t.points.find((p) => p.room === room)?.overall_score])),
  }));

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader eyebrow="Instructor" title="Analytics" description="Trends across completed exercises. All scores are experimental training metrics." />
      {q.isLoading || !d ? (
        <LoadingBlock rows={6} />
      ) : d.total_exercises === 0 ? (
        <Card><EmptyState icon={<BarChart3 />} title="No completed exercises yet" description="Analytics appear once exercises have ended." /></Card>
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard label="Exercises" value={d.total_exercises} icon={<BarChart3 />} hint={`${d.total_decisions} decisions`} />
            <StatCard label="Avg response time" value={`${d.average_response_time_s.toFixed(0)}s`} icon={<Clock />} hint="simulation time" />
            <StatCard label="Avg uncertainty at decision" value={d.average_uncertainty_at_decision.toFixed(0)} tone={uncertaintyTone(d.average_uncertainty_at_decision)} icon={<Gauge />} />
            <StatCard label="Avg coordination" value={d.average_coordination_score.toFixed(0)} tone={scoreTone(d.average_coordination_score)} icon={<Users />} />
            <StatCard label="Avg team score" value={d.average_team_score.toFixed(0)} tone={scoreTone(d.average_team_score)} hint={`${d.reports_generated} AAR reports`} />
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader title="Decision confidence distribution" />
              <CardBody className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={d.confidence_distribution}>
                    <CartesianGrid stroke="#222b37" vertical={false} />
                    <XAxis dataKey="range" {...axis} />
                    <YAxis allowDecimals={false} {...axis} />
                    <Tooltip {...tooltip} />
                    <Bar dataKey="count" name="Decisions" fill="#4fc1d6" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Communication degradation frequency" />
              <CardBody className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={d.degradation_frequency} layout="vertical" margin={{ left: 60 }}>
                    <CartesianGrid stroke="#222b37" horizontal={false} />
                    <XAxis type="number" allowDecimals={false} {...axis} />
                    <YAxis type="category" dataKey="type" width={160} {...axis} />
                    <Tooltip {...tooltip} />
                    <Bar dataKey="count" name="Disruptions" fill="#e5574e" radius={[0, 3, 3, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Delivery outcomes" />
              <CardBody className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={d.delivery_outcomes}>
                    <CartesianGrid stroke="#222b37" vertical={false} />
                    <XAxis dataKey="status" {...axis} />
                    <YAxis allowDecimals={false} {...axis} />
                    <Tooltip {...tooltip} />
                    <Bar dataKey="count" name="Deliveries" fill="#e3a63c" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Participant performance trends" description="Overall training score per exercise" />
              <CardBody className="h-64">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendData}>
                    <CartesianGrid stroke="#222b37" vertical={false} />
                    <XAxis dataKey="room" {...axis} />
                    <YAxis domain={[0, 100]} {...axis} />
                    <Tooltip {...tooltip} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {d.participant_trends.map((t, i) => (
                      <Line key={t.name} dataKey={t.name} stroke={PALETTE[i % PALETTE.length]} strokeWidth={2} connectNulls />
                    ))}
                  </LineChart>
                </ResponsiveContainer>
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
