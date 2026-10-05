"use client";

import { useEffect, useState } from "react";

/**
 * Display-only interpolation of the server's simulation clock between refetches.
 * The server remains authoritative; this just keeps the timer ticking smoothly.
 */
export function useSimClock(simTime: number | undefined, status: string | undefined, timeScale: number, fetchedAt: number) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (status !== "RUNNING") return;
    const id = setInterval(() => setNow(Date.now()), 500);
    return () => clearInterval(id);
  }, [status]);
  if (simTime === undefined) return 0;
  if (status !== "RUNNING") return simTime;
  return simTime + Math.max(0, (now - fetchedAt) / 1000) * timeScale;
}
