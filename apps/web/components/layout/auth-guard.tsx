"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { LoadingBlock } from "@/components/ui/feedback";
import { useMe } from "@/features/auth";
import { homeFor, useAuthStore } from "@/lib/auth-store";

/**
 * Client-side route guard (convenience only - the API enforces every permission).
 * Waits for session rehydration, validates the token with /auth/me and redirects
 * unauthenticated users to login and wrong roles to their own home.
 */
export function RequireRole({ roles, children }: { roles: string[]; children: React.ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const hydrated = useAuthStore((s) => s.hydrated);
  const user = useAuthStore((s) => s.user);
  const me = useMe(hydrated && Boolean(user));

  useEffect(() => {
    if (!hydrated) return;
    if (!user) {
      router.replace(`/login?next=${encodeURIComponent(window.location.pathname + window.location.search)}`);
    } else if (!roles.includes(user.role)) {
      router.replace(homeFor(user.role));
    }
  }, [hydrated, user, roles, router, pathname]);

  if (!hydrated || !user || !roles.includes(user.role) || (me.isLoading && !me.data)) {
    return (
      <div className="mx-auto max-w-5xl p-8">
        <LoadingBlock rows={4} />
      </div>
    );
  }
  return <>{children}</>;
}
