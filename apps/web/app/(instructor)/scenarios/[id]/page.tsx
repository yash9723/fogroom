"use client";

import { useRouter } from "next/navigation";
import { use } from "react";
import { BLANK_SCENARIO, ScenarioEditor } from "@/components/scenarios/scenario-editor";
import { ErrorState, LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { useSaveScenario, useScenario } from "@/features/scenarios";

export default function ScenarioEditPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
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
          if (isNew && saved.id) router.replace(`/scenarios/${saved.id}`);
        }}
      />
    </div>
  );
}
