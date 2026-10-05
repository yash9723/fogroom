"use client";

import { Plus, Rocket } from "lucide-react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useState } from "react";
import { RoomStatusBadge } from "@/components/status/indicators";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { Field, Input, Select } from "@/components/ui/form";
import { useCreateRoom, useLaunchDemo, useRooms } from "@/features/rooms";
import { useScenarios } from "@/features/scenarios";
import { relativeTime } from "@/lib/utils";

const SCALES = [1, 2, 5, 10];

function CreateDialog({ open, onOpenChange }: { open: boolean; onOpenChange: (v: boolean) => void }) {
  const router = useRouter();
  const scenarios = useScenarios();
  const create = useCreateRoom();
  const [scenarioId, setScenarioId] = useState("");
  const [name, setName] = useState("");
  const [scale, setScale] = useState(1);
  const chosen = scenarioId || scenarios.data?.[0]?.id || "";

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!chosen) return;
    const room = await create.mutateAsync({ scenario_id: chosen, name: name || undefined, time_scale: scale });
    onOpenChange(false);
    router.push(`/exercises/${room.id}`);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent title="Create exercise" description="A room code is generated for trainees to join.">
        <form onSubmit={submit} className="space-y-4">
          <Field label="Scenario" htmlFor="create-scenario">
            <Select id="create-scenario" value={chosen} onChange={(e) => setScenarioId(e.target.value)}>
              {scenarios.data?.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.difficulty.toLowerCase()})
                </option>
              ))}
            </Select>
          </Field>
          <Field label="Room name (optional)" htmlFor="create-name">
            <Input id="create-name" value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Cohort B - morning" />
          </Field>
          <Field label="Time scale" htmlFor="create-scale" hint="Speeds up the simulation clock for demonstrations.">
            <Select id="create-scale" value={scale} onChange={(e) => setScale(Number(e.target.value))}>
              {SCALES.map((s) => (
                <option key={s} value={s}>
                  ×{s} {s === 1 ? "(real time)" : ""}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex justify-end gap-2">
            <Button type="button" variant="ghost" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button type="submit" variant="primary" loading={create.isPending} disabled={!chosen}>
              Create room
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}

function ExercisesInner() {
  const params = useSearchParams();
  const router = useRouter();
  const rooms = useRooms();
  const launch = useLaunchDemo();
  const [open, setOpen] = useState(params.get("create") === "1");

  const groups = [
    { title: "Running", statuses: ["RUNNING", "PAUSED"] },
    { title: "Lobby", statuses: ["LOBBY"] },
    { title: "Completed", statuses: ["COMPLETED", "ARCHIVED"] },
  ];

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Instructor"
        title="Live exercises"
        description="Create rooms from scenario templates, invite trainees with the room code and run the exercise."
        actions={
          <>
            <Button
              onClick={async () => {
                const room = await launch.mutateAsync(1);
                router.push(`/exercises/${room.id}`);
              }}
              loading={launch.isPending}
            >
              <Rocket aria-hidden /> Launch Demo Exercise
            </Button>
            <Button variant="primary" onClick={() => setOpen(true)} data-testid="create-exercise">
              <Plus aria-hidden /> Create Exercise
            </Button>
          </>
        }
      />
      <CreateDialog open={open} onOpenChange={setOpen} />
      {rooms.isLoading ? (
        <LoadingBlock rows={5} />
      ) : !rooms.data?.length ? (
        <Card>
          <EmptyState title="No exercises yet" description="Launch the Operation Grey Signal demo to get started." />
        </Card>
      ) : (
        <div className="space-y-6">
          {groups.map((g) => {
            const list = rooms.data.filter((r) => g.statuses.includes(r.status));
            if (!list.length) return null;
            return (
              <section key={g.title}>
                <h2 className="mb-2 text-xs font-semibold uppercase tracking-wider text-muted">{g.title}</h2>
                <Card className="divide-y divide-line">
                  {list.map((r) => (
                    <Link
                      key={r.id}
                      href={g.title === "Completed" ? `/aar/${r.id}` : `/exercises/${r.id}`}
                      className="flex flex-wrap items-center justify-between gap-3 px-4 py-3 hover:bg-panel-2"
                    >
                      <div>
                        <div className="text-sm font-medium">{r.name}</div>
                        <div className="text-xs text-muted">
                          <span className="font-mono text-accent">{r.room_code}</span> · {r.scenario_name} ·{" "}
                          {r.participants.length} participants · created {relativeTime(r.created_at)}
                        </div>
                      </div>
                      <RoomStatusBadge status={r.status} />
                    </Link>
                  ))}
                </Card>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

export default function ExercisesPage() {
  return (
    <Suspense>
      <ExercisesInner />
    </Suspense>
  );
}
