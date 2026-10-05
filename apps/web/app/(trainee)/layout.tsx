"use client";

import { Inbox, MessagesSquare, PlayCircle, UserRound, Vote } from "lucide-react";
import { AppShell, type NavItem } from "@/components/layout/app-shell";
import { RequireRole } from "@/components/layout/auth-guard";

const NAV: NavItem[] = [
  { href: "/exercise", label: "Active Exercise", icon: PlayCircle },
  { href: "/messages", label: "Messages", icon: Inbox },
  { href: "/decisions", label: "Decision Log", icon: Vote },
  { href: "/team", label: "Team Communication", icon: MessagesSquare },
  { href: "/profile", label: "Profile", icon: UserRound },
];

export default function TraineeLayout({ children }: { children: React.ReactNode }) {
  return (
    <RequireRole roles={["TRAINEE"]}>
      <AppShell nav={NAV}>{children}</AppShell>
    </RequireRole>
  );
}
