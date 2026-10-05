"use client";

import { Save } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardBody } from "@/components/ui/card";
import { PageHeader } from "@/components/ui/feedback";
import { Field, Input } from "@/components/ui/form";
import { useUpdateProfile } from "@/features/auth";
import { toastError } from "@/features/rooms";
import { useAuthStore } from "@/lib/auth-store";

export default function ProfilePage() {
  const user = useAuthStore((s) => s.user);
  const update = useUpdateProfile();
  const [name, setName] = useState(user?.display_name ?? "");
  return (
    <div className="mx-auto max-w-xl">
      <PageHeader title="Profile" />
      <Card>
        <CardBody className="space-y-4">
          <div className="flex items-center gap-2 text-sm">
            <span className="text-muted">{user?.email}</span>
            <Badge tone="accent">{user?.role}</Badge>
          </div>
          <Field label="Display name" htmlFor="profile-name">
            <Input id="profile-name" value={name} onChange={(e) => setName(e.target.value)} />
          </Field>
          <Button
            variant="primary"
            loading={update.isPending}
            disabled={!name.trim()}
            onClick={() =>
              update.mutate(
                { display_name: name.trim() },
                { onSuccess: () => toast.success("Profile updated"), onError: (e) => toastError(e) },
              )
            }
          >
            <Save aria-hidden /> Save
          </Button>
        </CardBody>
      </Card>
    </div>
  );
}
