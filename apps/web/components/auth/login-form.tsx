"use client";

import { LogIn } from "lucide-react";
import { useState } from "react";
import { z } from "zod";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { ApiError } from "@/lib/api";

const schema = z.object({
  email: z.email("Enter a valid email address"),
  password: z.string().min(1, "Password is required"),
});

export type LoginValues = z.infer<typeof schema>;

/** Presentational login form - the caller decides what happens on submit. */
export function LoginForm({
  onSubmit,
  defaultEmail = "",
}: {
  onSubmit: (values: LoginValues) => Promise<void>;
  defaultEmail?: string;
}) {
  const [email, setEmail] = useState(defaultEmail);
  const [password, setPassword] = useState("");
  const [errors, setErrors] = useState<Partial<Record<keyof LoginValues, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setFormError(null);
    const parsed = schema.safeParse({ email, password });
    if (!parsed.success) {
      const fieldErrors: Partial<Record<keyof LoginValues, string>> = {};
      for (const issue of parsed.error.issues) {
        const key = issue.path[0] as keyof LoginValues;
        fieldErrors[key] ??= issue.message;
      }
      setErrors(fieldErrors);
      return;
    }
    setErrors({});
    setPending(true);
    try {
      await onSubmit(parsed.data);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Sign in failed. Please try again.");
    } finally {
      setPending(false);
    }
  };

  return (
    <form onSubmit={handle} noValidate className="space-y-4" aria-label="Sign in">
      <Field label="Email" htmlFor="login-email" error={errors.email}>
        <Input
          id="login-email"
          type="email"
          autoComplete="username"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={Boolean(errors.email)}
        />
      </Field>
      <Field label="Password" htmlFor="login-password" error={errors.password}>
        <Input
          id="login-password"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          aria-invalid={Boolean(errors.password)}
        />
      </Field>
      {formError && (
        <p role="alert" className="rounded-md border border-crit/40 bg-crit-soft px-3 py-2 text-sm text-crit">
          {formError}
        </p>
      )}
      <Button type="submit" variant="primary" className="w-full" loading={pending}>
        <LogIn aria-hidden /> Sign in
      </Button>
    </form>
  );
}
