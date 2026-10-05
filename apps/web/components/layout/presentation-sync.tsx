"use client";

import { useEffect } from "react";
import { useUiStore } from "@/lib/ui-store";

/** Applies presentation mode (?presentation=true or the settings toggle) to <html>. */
export function PresentationSync() {
  const presentation = useUiStore((s) => s.presentation);
  const setPresentation = useUiStore((s) => s.setPresentation);

  useEffect(() => {
    const param = new URLSearchParams(window.location.search).get("presentation");
    if (param === "true") setPresentation(true);
    if (param === "false") setPresentation(false);
  }, [setPresentation]);

  useEffect(() => {
    document.documentElement.dataset.presentation = presentation ? "true" : "false";
  }, [presentation]);

  return null;
}
