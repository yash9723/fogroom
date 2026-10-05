"use client";

import { GraduationCap, UserRound } from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { demoLogin, useDemoConfig, type Persona } from "@/features/auth";
import { toastError } from "@/features/rooms";
import { homeFor } from "@/lib/auth-store";

const PERSONAS: { persona: Persona; label: string; hint: string }[] = [
  { persona: "instructor", label: "Instructor", hint: "Runs the exercise" },
  { persona: "alpha", label: "Coordinator Alpha", hint: "Trainee" },
  { persona: "bravo", label: "Logistics Bravo", hint: "Trainee" },
  { persona: "charlie", label: "Communications Charlie", hint: "Trainee" },
];

/** One-click demo sign-in (only when the server runs with DEMO_MODE=true). */
export function DemoPersonas() {
  const router = useRouter();
  const config = useDemoConfig();
  const [busy, setBusy] = useState<Persona | null>(null);
  if (!config.data?.demo_mode) return null;

  const go = async (persona: Persona) => {
    setBusy(persona);
    try {
      const pair = await demoLogin(persona);
      router.push(homeFor(pair.user.role));
    } catch (e) {
      toastError(e, "Demo login failed");
    } finally {
      setBusy(null);
    }
  };

  return (
    <div>
      <div className="mb-2 flex items-center gap-2 text-xs uppercase tracking-wider text-muted">
        <span className="h-px flex-1 bg-line" /> Demo accounts <span className="h-px flex-1 bg-line" />
      </div>
      <div className="grid grid-cols-2 gap-2">
        {PERSONAS.map((p) => (
          <Button
            key={p.persona}
            variant="secondary"
            size="sm"
            className="h-auto justify-start py-2 text-left"
            loading={busy === p.persona}
            onClick={() => go(p.persona)}
            data-testid={`demo-${p.persona}`}
          >
            {p.persona === "instructor" ? <GraduationCap aria-hidden /> : <UserRound aria-hidden />}
            <span className="flex flex-col">
              <span className="text-xs font-medium">{p.label}</span>
              <span className="text-[10px] font-normal text-muted">{p.hint}</span>
            </span>
          </Button>
        ))}
      </div>
    </div>
  );
}
