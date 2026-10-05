"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { DemoPersonas } from "@/components/auth/demo-personas";
import { LoginForm } from "@/components/auth/login-form";
import { Logo } from "@/components/brand/logo";
import { login } from "@/features/auth";
import { homeFor } from "@/lib/auth-store";

function LoginInner() {
  const router = useRouter();
  const params = useSearchParams();
  const next = params.get("next");

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-xl border border-line bg-panel p-6">
        <Logo subtitle className="mb-6" />
        <h1 className="text-base font-semibold">Sign in to FOGROOM</h1>
        <p className="mb-5 mt-1 text-xs text-muted">Your session is kept in this browser tab only.</p>
        <LoginForm
          onSubmit={async ({ email, password }) => {
            const pair = await login(email, password);
            const safeNext = next && next.startsWith("/") && !next.startsWith("//") ? next : null;
            router.replace(safeNext ?? homeFor(pair.user.role));
          }}
        />
        <p className="mt-4 text-center text-xs text-muted">
          No account?{" "}
          <Link href="/register" className="text-accent hover:underline">
            Register as a trainee
          </Link>
        </p>
        <div className="mt-6">
          <DemoPersonas />
        </div>
      </div>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}
