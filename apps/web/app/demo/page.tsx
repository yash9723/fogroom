"use client";

import { routes } from "@/lib/routes";
import { Loader2 } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useRef, useState } from "react";
import { Logo } from "@/components/brand/logo";
import { ErrorState } from "@/components/ui/feedback";
import { demoLogin, type Persona } from "@/features/auth";
import { joinRoomByCode } from "@/features/rooms";
import { ApiError } from "@/lib/api";
import { homeFor } from "@/lib/auth-store";

const VALID: Persona[] = ["instructor", "alpha", "bravo", "charlie"];

/**
 * Demo launcher used by "Open Alpha / Bravo / Charlie demo" buttons. Each opens in a new
 * tab (fresh sessionStorage), signs in as the persona and joins the room code.
 */
function DemoInner() {
  const params = useSearchParams();
  const router = useRouter();
  const [failure, setError] = useState<string | null>(null);
  const started = useRef(false);
  const persona = params.get("persona") as Persona | null;
  const code = params.get("code");
  const valid = Boolean(persona && VALID.includes(persona));
  const error = valid ? failure : "Unknown demo persona.";

  useEffect(() => {
    if (started.current || !valid || !persona) return;
    started.current = true;
    (async () => {
      try {
        const pair = await demoLogin(persona);
        if (persona !== "instructor" && code) {
          const joined = await joinRoomByCode(code);
          router.replace(routes.traineeExercise(joined.room.id));
        } else {
          router.replace(homeFor(pair.user.role));
        }
      } catch (e) {
        setError(e instanceof ApiError ? e.message : "Demo launch failed.");
      }
    })();
  }, [valid, persona, code, router]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 px-4">
      <Logo subtitle />
      {error ? (
        <ErrorState message={error} />
      ) : (
        <p className="flex items-center gap-2 text-sm text-muted">
          <Loader2 className="size-4 animate-spin" aria-hidden /> Preparing demo session…
        </p>
      )}
    </div>
  );
}

export default function DemoPage() {
  return (
    <Suspense>
      <DemoInner />
    </Suspense>
  );
}
