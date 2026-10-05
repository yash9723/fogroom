"use client";

import { LogIn } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { ApiError } from "@/lib/api";

const CODE = /^[A-Za-z]{2,5}-?\d{2,3}$/;

/** Join an exercise by room code (e.g. GREY-42). */
export function JoinForm({ onJoin }: { onJoin: (code: string) => Promise<void> }) {
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const normalized = code.trim().toUpperCase();
    if (!CODE.test(normalized)) {
      setError("Enter the room code shown by your instructor, e.g. GREY-42");
      return;
    }
    setError(null);
    setPending(true);
    try {
      await onJoin(normalized.includes("-") ? normalized : normalized.replace(/(\D+)(\d+)/, "$1-$2"));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not join the exercise");
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={submit} noValidate className="flex flex-col gap-3 sm:flex-row sm:items-end" aria-label="Join exercise">
      <Field label="Room code" htmlFor="room-code" error={error} className="flex-1">
        <Input
          id="room-code"
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="GREY-42"
          autoComplete="off"
          className="font-mono uppercase tracking-widest"
          aria-invalid={Boolean(error)}
        />
      </Field>
      <Button type="submit" variant="primary" loading={pending} className={error ? "sm:mb-5" : undefined}>
        <LogIn aria-hidden /> Join exercise
      </Button>
    </form>
  );
}
