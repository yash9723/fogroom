"use client";

import { Activity, GitCompareArrows, History, Users } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { DemoPersonas } from "@/components/auth/demo-personas";
import { LoginForm } from "@/components/auth/login-form";
import { Logo } from "@/components/brand/logo";
import { login } from "@/features/auth";
import { homeFor, useAuthStore } from "@/lib/auth-store";

const FEATURES = [
  {
    icon: Activity,
    title: "Controlled Communication Degradation",
    text: "Delay, drop, reroute or contradict information per recipient - deterministic, auditable and replayable.",
  },
  {
    icon: Users,
    title: "Multiplayer Decision Training",
    text: "An instructor and a team of trainees in one live room, each with their own role, channels and decisions.",
  },
  {
    icon: GitCompareArrows,
    title: "Information-State Digital Twin",
    text: "Reconstruct exactly what every participant knew - and did not know - at the moment they decided.",
  },
  {
    icon: History,
    title: "After Action Replay",
    text: "Scrub the timeline and switch between global truth and each trainee's view to debrief decisions in context.",
  },
];

export default function LandingPage() {
  const router = useRouter();
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);

  useEffect(() => {
    if (hydrated && user) router.replace(homeFor(user.role));
  }, [hydrated, user, router]);

  return (
    <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-5 py-8 lg:px-8">
      <header className="flex items-center justify-between">
        <Logo />
        <span className="hidden text-xs text-muted sm:block">Smart India Hackathon · SIH26248</span>
      </header>

      <main className="grid flex-1 items-center gap-10 py-10 lg:grid-cols-[1.2fr_1fr] lg:gap-16">
        <section>
          <p className="mb-4 font-mono text-xs uppercase tracking-[0.3em] text-accent">Training simulation platform</p>
          <h1 className="font-mono text-5xl font-semibold tracking-[0.12em] text-fg sm:text-6xl">FOGROOM</h1>
          <p className="mt-3 text-xl text-fg/90">Decision Training Under Information Uncertainty</p>
          <p className="mt-5 max-w-xl text-sm leading-relaxed text-muted">
            Train teams to make high-quality decisions when communication becomes delayed, incomplete,
            contradictory, or unavailable - then review not just <em>what</em> was decided, but what information
            was actually available when it was decided.
          </p>
          <div className="mt-8 grid gap-3 sm:grid-cols-2">
            {FEATURES.map((f) => (
              <div key={f.title} className="rounded-lg border border-line bg-panel/70 p-4">
                <f.icon className="size-4 text-accent" aria-hidden />
                <h2 className="mt-2 text-sm font-semibold">{f.title}</h2>
                <p className="mt-1 text-xs leading-relaxed text-muted">{f.text}</p>
              </div>
            ))}
          </div>
        </section>

        <section aria-labelledby="signin-title" className="rounded-xl border border-line bg-panel p-6 shadow-2xl shadow-black/40">
          <h2 id="signin-title" className="text-base font-semibold">
            Sign in
          </h2>
          <p className="mb-5 mt-1 text-xs text-muted">Instructors and trainees use the same sign-in.</p>
          <LoginForm
            onSubmit={async ({ email, password }) => {
              const pair = await login(email, password);
              router.push(homeFor(pair.user.role));
            }}
          />
          <p className="mt-4 text-center text-xs text-muted">
            New trainee?{" "}
            <Link href="/register" className="text-accent hover:underline">
              Create an account
            </Link>
          </p>
          <div className="mt-6">
            <DemoPersonas />
          </div>
        </section>
      </main>

      <footer className="border-t border-line pt-4 text-[11px] text-subtle">
        All scenarios, places and organisations are fictional. Scores are experimental training metrics.
      </footer>
    </div>
  );
}
