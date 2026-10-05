"use client";

import { useRouter } from "next/navigation";
import { WithQueryId } from "@/components/layout/with-query-id";
import { BLANK_SCENARIO, ScenarioEditor } from "@/components/scenarios/scenario-editor";
import { ErrorState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useSaveScenario, useScenario } from "@/features/scenarios";
import { routes } from "@/lib/routes";

export default function ScenarioEditPage() {
  return <WithQueryId render={(id) => <ScenarioEdit key={id} id={id} />} />;
}

function ScenarioEdit({ id }: { id: string }) {
  const isNew = id === "new";
  const router = useRouter();
  const q = useScenario(isNew ? undefined : id);
  const save = useSaveScenario();

  if (!isNew && q.error) return <ErrorState message={q.error.message} />;
  if (!isNew && !q.data) return <LoadingBlock rows={6} />;
  const initial = isNew ? BLANK_SCENARIO : q.data!;

  return (
    <div className="mx-auto max-w-6xl">
      <PageHeader eyebrow="Scenario builder" title={isNew ? "New scenario" : initial.name} />
      <ScenarioEditor
        key={initial.id ?? "new"}
        initial={initial}
        saving={save.isPending}
        onSave={async (doc) => {
          const saved = await save.mutateAsync(doc);
          if (isNew && saved.id) router.replace(routes.scenario(saved.id));
        }}
      />
    </div>
  );
}
