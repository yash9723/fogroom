"use client";

import { BarChart3, ClipboardList, LayoutDashboard, PlayCircle, Settings, ScrollText } from "lucide-react";
import { AppShell, type NavItem } from "@/components/layout/app-shell";
import { RequireRole } from "@/components/layout/auth-guard";

const NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/scenarios", label: "Scenarios", icon: ScrollText },
  { href: "/exercises", label: "Live Exercises", icon: PlayCircle },
  { href: "/aar", label: "AAR Reports", icon: ClipboardList },
  { href: "/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/settings", label: "Settings", icon: Settings },
];

export default function InstructorLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireRole roles={["INSTRUCTOR", "ADMIN"]}>
      <AppShell nav={NAV}>{children}</AppShell>
    </RequireRole>
  );
}
