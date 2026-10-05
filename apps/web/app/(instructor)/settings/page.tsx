"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { MonitorPlay, Shield, UserCog } from "lucide-react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody, CardHeader } from "@/components/ui/card";
import { LoadingBlock, PageHeader } from "@/components/ui/feedback";
import { Select } from "@/components/ui/form";
import { toastError } from "@/features/rooms";
import { api } from "@/lib/api";
import { useAuthStore } from "@/lib/auth-store";
import type { User } from "@/lib/types";
import { useUiStore } from "@/lib/ui-store";

function UserAdmin() {
  const qc = useQueryClient();
  const users = useQuery({ queryKey: ["admin-users"], queryFn: () => api<User[]>("/admin/users") });
  const update = useMutation({
    mutationFn: ({ id, body }: { id: string; body: { role?: string; is_active?: boolean } }) =>
      api<User>(`/admin/users/${id}`, { method: "PATCH", body }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      toast.success("User updated");
    },
    onError: (e) => toastError(e),
  });
  const me = useAuthStore((s) => s.user);
  if (users.isLoading) return <LoadingBlock rows={3} />;
  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b border-line text-left text-xs text-muted">
          <th className="py-2 font-medium">User</th>
          <th className="py-2 font-medium">Role</th>
          <th className="py-2 font-medium">Status</th>
        </tr>
      </thead>
      <tbody className="divide-y divide-line">
        {users.data?.map((u) => (
          <tr key={u.id}>
            <td className="py-2">
              <div>{u.display_name}</div>
              <div className="text-xs text-muted">{u.email}</div>
            </td>
            <td className="py-2">
              <Select
                aria-label={`Role for ${u.email}`}
                className="h-8 w-40"
                value={u.role}
                disabled={u.id === me?.id}
                onChange={(e) => update.mutate({ id: u.id, body: { role: e.target.value } })}
              >
                <option>TRAINEE</option>
                <option>INSTRUCTOR</option>
                <option>ADMIN</option>
              </Select>
            </td>
            <td className="py-2">
              <Button
                size="sm"
                variant="ghost"
                disabled={u.id === me?.id}
                onClick={() => update.mutate({ id: u.id, body: { is_active: !u.is_active } })}
              >
                {u.is_active ? <Badge tone="ok">Active</Badge> : <Badge tone="off">Disabled</Badge>}
              </Button>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}

export default function SettingsPage() {
  const user = useAuthStore((s) => s.user);
  const presentation = useUiStore((s) => s.presentation);
  const setPresentation = useUiStore((s) => s.setPresentation);
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <PageHeader eyebrow="Instructor" title="Settings" />
      <Card>
        <CardHeader title="Presentation mode" description="Larger text and key indicators for projectors; hides navigation chrome. Also available via ?presentation=true." icon={<MonitorPlay />} />
        <CardBody>
          <Button variant={presentation ? "primary" : "secondary"} onClick={() => setPresentation(!presentation)} aria-pressed={presentation}>
            {presentation ? "Presentation mode on" : "Enable presentation mode"}
          </Button>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Account" icon={<UserCog />} />
        <CardBody className="text-sm">
          {user?.display_name} · {user?.email} · <Badge tone="accent">{user?.role}</Badge>
        </CardBody>
      </Card>
      {user?.role === "ADMIN" && (
        <Card>
          <CardHeader title="User management" description="Promote trainees to instructors or disable accounts." icon={<Shield />} />
          <CardBody>
            <UserAdmin />
          </CardBody>
        </Card>
      )}
    </div>
  );
}
