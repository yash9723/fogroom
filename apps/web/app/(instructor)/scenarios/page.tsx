"use client";

import { routes } from "@/lib/routes";
import { Copy, Pencil, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useDeleteScenario, useDuplicateScenario, useScenarios } from "@/features/scenarios";

export default function ScenariosPage() {
  const list = useScenarios();
  const dup = useDuplicateScenario();
  const del = useDeleteScenario();
  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader
        eyebrow="Instructor"
        title="Scenarios"
        description="Fictional scenario templates: roles, channels, phases, timed events with controlled variants and decision points."
        actions={
          <Button asChild variant="primary">
            <Link href={routes.scenario("new")}><Plus aria-hidden /> New scenario</Link>
          </Button>
        }
      />
      {list.isLoading ? (
        <LoadingBlock rows={4} />
      ) : !list.data?.length ? (
        <Card><EmptyState title="No scenarios" description="Run the seed command to load Operation Grey Signal." /></Card>
      ) : (
        <div className="grid gap-4 md:grid-cols-2">
          {list.data.map((s) => (
            <Card key={s.id} className="flex flex-col p-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h2 className="text-base font-semibold">{s.name}</h2>
                  <p className="text-xs text-muted">{s.category} · ~{s.estimated_duration_minutes} min</p>
                </div>
                <Badge tone={s.difficulty === "ADVANCED" ? "crit" : s.difficulty === "BEGINNER" ? "ok" : "warn"}>{s.difficulty}</Badge>
              </div>
              <p className="mt-2 line-clamp-3 flex-1 text-sm text-muted">{s.description}</p>
              <div className="mt-3 flex flex-wrap gap-1.5 text-[11px]">
                <Badge>{s.role_count} roles</Badge>
                <Badge>{s.channel_count} channels</Badge>
                <Badge>{s.event_count} events</Badge>
                <Badge>{s.decision_count} decision points</Badge>
              </div>
              <div className="mt-4 flex gap-2">
                <Button asChild size="sm" variant="secondary"><Link href={routes.scenario(s.id)}><Pencil aria-hidden /> Edit</Link></Button>
                <Button size="sm" variant="ghost" onClick={() => dup.mutate(s.id)}><Copy aria-hidden /> Duplicate</Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => {
                    if (window.confirm(`Delete "${s.name}"? Rooms keep their own frozen copy.`)) del.mutate(s.id);
                  }}
                >
                  <Trash2 aria-hidden /> Delete
                </Button>
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}
