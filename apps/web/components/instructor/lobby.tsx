"use client";

import { Copy, ExternalLink, Play, UserMinus, Users } from "lucide-react";
import { toast } from "sonner";
import { PresenceBadge, RoomStatusBadge } from "@/components/status/indicators";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { EmptyState, PageHeader } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { useLifecycle, useRemoveParticipant, useUpdateParticipant } from "@/features/rooms";
import { DEMO_MODE } from "@/lib/config";
import type { RoomSummary } from "@/lib/types";

const DEMO_PERSONAS = [
  { persona: "alpha", label: "Open Alpha Demo" },
  { persona: "bravo", label: "Open Bravo Demo" },
  { persona: "charlie", label: "Open Charlie Demo" },
];

export function Lobby({ room }: { room: RoomSummary }) {
  const lifecycle = useLifecycle(room.id);
  const update = useUpdateParticipant(room.id);
  const remove = useRemoveParticipant(room.id);

  const copyCode = async () => {
    try {
      await navigator.clipboard.writeText(room.room_code);
      toast.success("Room code copied");
    } catch {
      toast.error("Clipboard unavailable");
    }
  };

  const openDemo = (persona: string) => {
    // noopener => fresh browsing context => separate sessionStorage session per tab.
    window.open(`/demo?persona=${persona}&code=${encodeURIComponent(room.room_code)}`, "_blank", "noopener");
  };

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Exercise lobby"
        title={room.name}
        description={room.scenario_description ?? undefined}
        actions={
          <Button
            variant="primary"
            size="lg"
            onClick={() => lifecycle.mutate("start")}
            loading={lifecycle.isPending}
            disabled={!room.participants.length}
            data-testid="start-exercise"
          >
            <Play aria-hidden /> Start exercise
          </Button>
        }
      />
      <div className="grid gap-6 lg:grid-cols-[340px_1fr]">
        <div className="space-y-6">
          <Card>
            <CardBody>
              <div className="text-xs uppercase tracking-wider text-muted">Room code</div>
              <div className="mt-1 flex items-center gap-3">
                <span className="font-mono text-4xl font-semibold tracking-[0.15em] text-accent" data-testid="room-code">
                  {room.room_code}
                </span>
                <Button variant="ghost" size="icon" onClick={copyCode} aria-label="Copy room code">
                  <Copy />
                </Button>
              </div>
              <ol className="mt-4 list-decimal space-y-1 pl-4 text-xs text-muted">
                <li>Trainees sign in at FOGROOM.</li>
                <li>
                  Open <strong className="text-fg">Active Exercise</strong> and enter the code.
                </li>
                <li>Assign roles below, then start the exercise.</li>
              </ol>
              <dl className="mt-4 grid grid-cols-2 gap-2 text-xs">
                <dt className="text-muted">Scenario</dt>
                <dd>{room.scenario_name}</dd>
                <dt className="text-muted">Instructor</dt>
                <dd>{room.instructor?.display_name}</dd>
                <dt className="text-muted">Status</dt>
                <dd>
                  <RoomStatusBadge status={room.status} />
                </dd>
                <dt className="text-muted">Time scale</dt>
                <dd className="font-mono">×{room.time_scale}</dd>
              </dl>
            </CardBody>
          </Card>
          {DEMO_MODE && (
            <Card>
              <CardHeader title="Single-laptop demo" description="Each opens a separate trainee session in a new tab." />
              <CardBody className="grid gap-2">
                {DEMO_PERSONAS.map((d) => (
                  <Button key={d.persona} variant="secondary" onClick={() => openDemo(d.persona)} data-testid={`open-demo-${d.persona}`}>
                    <ExternalLink aria-hidden /> {d.label}
                  </Button>
                ))}
              </CardBody>
            </Card>
          )}
        </div>

        <Card>
          <CardHeader
            title="Participants"
            description={`${room.participants.length} joined · ${room.roles.length} scenario roles`}
            icon={<Users />}
          />
          {room.participants.length === 0 ? (
            <EmptyState title="Waiting for trainees" description="Share the room code. Participants appear here in real time." />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-line text-left text-xs text-muted">
                    <th className="px-4 py-2 font-medium">Trainee</th>
                    <th className="px-4 py-2 font-medium">Role</th>
                    <th className="px-4 py-2 font-medium">Connection</th>
                    <th className="px-4 py-2 font-medium">Ready</th>
                    <th className="px-4 py-2" />
                  </tr>
                </thead>
                <tbody className="divide-y divide-line">
                  {room.participants.map((p) => (
                    <tr key={p.id}>
                      <td className="px-4 py-2.5">
                        <div className="font-medium">{p.display_name}</div>
                        <div className="font-mono text-xs text-accent">{p.callsign}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        <Select
                          aria-label={`Role for ${p.display_name}`}
                          value={p.assigned_role ?? ""}
                          onChange={(e) => update.mutate({ participantId: p.id, role_key: e.target.value })}
                          className="h-8 w-52"
                        >
                          <option value="" disabled>
                            Unassigned
                          </option>
                          {room.roles.map((r) => (
                            <option key={r.key} value={r.key}>
                              {r.name}
                            </option>
                          ))}
                        </Select>
                      </td>
                      <td className="px-4 py-2.5">
                        <PresenceBadge status={p.connection_status} />
                      </td>
                      <td className="px-4 py-2.5">
                        {p.is_ready ? <Badge tone="ok">Ready</Badge> : <Badge tone="off">Not ready</Badge>}
                      </td>
                      <td className="px-4 py-2.5 text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => remove.mutate(p.id)}
                          aria-label={`Remove ${p.display_name}`}
                        >
                          <UserMinus aria-hidden /> Remove
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </Card>
      </div>
    </div>
  );
}
