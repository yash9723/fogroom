"use client";

import { useSearchParams } from "next/navigation";
import { Suspense, type ReactNode } from "react";
import { EmptyState, LoadingBlock } from "@/components/ui/feedback";

function Inner({ render }: { render: (id: string) => ReactNode }) {
  const id = useSearchParams().get("id");
  if (!id) return <EmptyState title="Nothing selected" description="This page needs an ?id= parameter." />;
  return <>{render(id)}</>;
}

/** Reads the entity id from `?id=` (static-export friendly replacement for [id] routes). */
export function WithQueryId({ render }: { render: (id: string) => ReactNode }) {
  return (
    <Suspense fallback={<LoadingBlock rows={6} />}>
      <Inner render={render} />
    </Suspense>
  );
}
