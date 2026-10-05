"use client";

import { routes } from "@/lib/routes";
import { ClipboardList, Gauge, PlayCircle, Plus, Rocket, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { RoomStatusBadge } from "@/components/status/indicators";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader, StatCard } from "@/components/ui/card";
import { EmptyState, ErrorState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useDashboard } from "@/features/analytics";
import { useLaunchDemo } from "@/features/rooms";
import type { RoomBrief } from "@/lib/types";
import { relativeTime, scoreTone } from "@/lib/utils";

function RoomList({ rooms, empty, hrefFor }: { rooms: RoomBrief[]; empty: string; hrefFor: (r: RoomBrief) => string }) {
  if (!rooms.length) return <EmptyState title={empty} className="py-6" />;
  return (
    <ul className="divide-y divide-line">
      {rooms.map((r) => (
        <li key={r.id}>
          <Link href={hrefFor(r)} className="flex items-center justify-between gap-3 px-4 py-3 hover:bg-panel-2">
            <div className="min-w-0">
              <div className="truncate text-sm font-medium">{r.name}</div>
              <div className="text-xs text-muted">
                <span className="font-mono">{r.room_code}</span> · {r.scenario_name} · {relativeTime(r.started_at ?? r.created_at)}
              </div>
            </div>
            <RoomStatusBadge status={r.status} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const { data, isLoading, error, refetch } = useDashboard();
  const launch = useLaunchDemo();

  const launchDemo = async () => {
    const room = await launch.mutateAsync(1);
    router.push(routes.exercise(room.id));
  };

  return (
    <div className="mx-auto max-w-7xl">
      <PageHeader
        eyebrow="Instructor"
        title="Dashboard"
        description="Run decision-training exercises under degraded communications and review what each trainee actually knew."
        actions={
          <>
            {data?.active[0] && (
              <Button asChild variant="secondary">
                <Link href={routes.exercise(data.active[0].id)}>
                  <PlayCircle aria-hidden /> Open Live Exercise
                </Link>
              </Button>
            )}
            <Button variant="secondary" onClick={launchDemo} loading={launch.isPending} data-testid="launch-demo">
              <Rocket aria-hidden /> Launch Demo Exercise
            </Button>
            <Button asChild variant="primary">
              <Link href="/exercises?create=1">
                <Plus aria-hidden /> Create Exercise
              </Link>
            </Button>
          </>
        }
      />

      {error ? (
        <ErrorState message={error.message} action={<Button size="sm" onClick={() => refetch()}>Retry</Button>} />
      ) : isLoading || !data ? (
        <LoadingBlock rows={6} />
      ) : (
        <div className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Active exercises" value={data.counts.active} icon={<PlayCircle />} tone={data.counts.active ? "ok" : "off"} />
            <StatCard label="Completed exercises" value={data.counts.completed} icon={<ClipboardList />} />
            <StatCard label="AAR reports" value={data.counts.reports} icon={<ClipboardList />} />
            <StatCard
              label="Avg team score"
              value={data.average_team_score === null ? "-" : data.average_team_score.toFixed(0)}
              hint="Experimental training metric"
              icon={<Gauge />}
              tone={scoreTone(data.average_team_score)}
            />
          </div>

          <div className="grid gap-6 xl:grid-cols-3">
            <Card>
              <CardHeader title="Active exercises" icon={<PlayCircle />} />
              <RoomList rooms={data.active} empty="No exercise is running" hrefFor={(r) => routes.exercise(r.id)} />
            </Card>
            <Card>
              <CardHeader title="Scheduled (lobby)" description="Rooms waiting for trainees" icon={<Users />} />
              <RoomList rooms={data.scheduled} empty="No rooms in lobby" hrefFor={(r) => routes.exercise(r.id)} />
            </Card>
            <Card>
              <CardHeader title="Completed exercises" icon={<ClipboardList />} />
              <RoomList rooms={data.completed.slice(0, 6)} empty="No completed exercises yet" hrefFor={(r) => routes.aar(r.id)} />
            </Card>
          </div>

          <div className="grid gap-6 xl:grid-cols-2">
            <Card>
              <CardHeader title="Recent AAR reports" icon={<ClipboardList />} />
              {data.recent_reports.length ? (
                <ul className="divide-y divide-line">
                  {data.recent_reports.map((r) => (
                    <li key={r.room_id}>
                      <Link href={routes.aar(r.room_id)} className="block px-4 py-3 hover:bg-panel-2">
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-medium">{r.room_name}</span>
                          <span className="font-mono text-sm tabular text-accent">{r.team_score.toFixed(0)}</span>
                        </div>
                        <p className="mt-1 line-clamp-2 text-xs text-muted">{r.summary}</p>
                      </Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <EmptyState title="No reports yet" description="Reports are generated after an exercise ends." />
              )}
            </Card>
            <Card>
              <CardHeader title="Recent participants" icon={<Users />} />
              {data.recent_participants.length ? (
                <CardBody className="grid gap-2 sm:grid-cols-2">
                  {data.recent_participants.map((p) => (
                    <div key={p.user_id} className="rounded-md border border-line bg-panel-2 px-3 py-2">
                      <div className="text-sm font-medium">{p.display_name}</div>
                      <div className="text-xs text-muted">
                        {p.callsign} · {p.room_name}
                      </div>
                    </div>
                  ))}
                </CardBody>
              ) : (
                <EmptyState title="No participants yet" />
              )}
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
