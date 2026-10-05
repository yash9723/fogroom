"use client";

import type { LucideIcon } from "lucide-react";
import { LogOut, Menu, MonitorPlay, X } from "lucide-react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { logout } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import { useUiStore } from "@/lib/ui-store";
import { cn } from "@/lib/utils";

export type NavItem = { href: string; label: string; icon: LucideIcon };

export function AppShell({ nav, children }: { nav: NavItem[]; children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const user = useAuthStore((s) => s.user);
  const presentation = useUiStore((s) => s.presentation);
  const setPresentation = useUiStore((s) => s.setPresentation);
  const [open, setOpen] = useState(false);

  const signOut = async () => {
    await logout();
    router.replace("/login");
  };

  const navList = (
    <nav aria-label="Main" className="flex flex-col gap-0.5">
      {nav.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            onClick={() => setOpen(false)}
            aria-current={active ? "page" : undefined}
            className={cn(
              "flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors",
              active ? "bg-panel-3 text-fg" : "text-muted hover:bg-panel-2 hover:text-fg",
            )}
          >
            <Icon className={cn("size-4", active ? "text-accent" : "text-subtle")} aria-hidden />
            {item.label}
          </Link>
        );
      })}
    </nav>
  );

  return (
    <div className="flex min-h-screen">
      <aside className="hide-in-presentation sticky top-0 hidden h-screen w-56 shrink-0 flex-col border-r border-line bg-panel/80 px-3 py-4 lg:flex">
        <Link href={nav[0]?.href ?? "/"} className="mb-6 px-2">
          <Logo subtitle />
        </Link>
        {navList}
        <div className="mt-auto space-y-3 border-t border-line pt-4">
          <div className="px-2">
            <div className="truncate text-sm font-medium">{user?.display_name}</div>
            <div className="mt-1 flex items-center gap-2">
              <Badge tone="accent">{user?.role}</Badge>
            </div>
          </div>
          <Button variant="ghost" size="sm" className="w-full justify-start" onClick={signOut}>
            <LogOut aria-hidden /> Sign out
          </Button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-12 items-center justify-between gap-3 border-b border-line bg-bg/90 px-4 backdrop-blur">
          <div className="flex items-center gap-2 lg:hidden">
            <Button variant="ghost" size="icon" aria-label="Open navigation" onClick={() => setOpen(true)}>
              <Menu />
            </Button>
            <Logo />
          </div>
          <div className="hidden text-xs text-muted lg:block">Fictional training environment · SIH26248</div>
          <div className="flex items-center gap-2">
            <Button
              variant={presentation ? "primary" : "ghost"}
              size="sm"
              onClick={() => setPresentation(!presentation)}
              aria-pressed={presentation}
              title="Projector-friendly presentation mode"
            >
              <MonitorPlay aria-hidden /> <span className="hidden sm:inline">Presentation</span>
            </Button>
            <Button variant="ghost" size="sm" className="lg:hidden" onClick={signOut} aria-label="Sign out">
              <LogOut />
            </Button>
          </div>
        </header>

        {open && (
          <div className="fixed inset-0 z-40 bg-black/60 lg:hidden" onClick={() => setOpen(false)}>
            <div className="h-full w-64 border-r border-line bg-panel p-4" onClick={(e) => e.stopPropagation()}>
              <div className="mb-6 flex items-center justify-between">
                <Logo />
                <Button variant="ghost" size="icon" aria-label="Close navigation" onClick={() => setOpen(false)}>
                  <X />
                </Button>
              </div>
              {navList}
            </div>
          </div>
        )}

        <main id="main" className="flex-1 px-4 py-6 lg:px-6">
          {children}
        </main>
      </div>
    </div>
  );
}
