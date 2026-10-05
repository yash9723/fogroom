"use client";

import { UserPlus } from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { z } from "zod";
import { Logo } from "@/components/brand/logo";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { register } from "@/features/auth";
import { ApiError } from "@/lib/api";

const schema = z.object({
  display_name: z.string().trim().min(1, "Enter your name").max(120),
  email: z.email("Enter a valid email address"),
  password: z
    .string()
    .min(8, "At least 8 characters")
    .regex(/[A-Za-z]/, "Include a letter")
    .regex(/[0-9]/, "Include a number"),
});

type Values = z.infer<typeof schema>;

export default function RegisterPage() {
  const router = useRouter();
  const [values, setValues] = useState<Values>({ display_name: "", email: "", password: "" });
  const [errors, setErrors] = useState<Partial<Record<keyof Values, string>>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    const parsed = schema.safeParse(values);
    if (!parsed.success) {
      const next: Partial<Record<keyof Values, string>> = {};
      parsed.error.issues.forEach((i) => (next[i.path[0] as keyof Values] ??= i.message));
      setErrors(next);
      return;
    }
    setErrors({});
    setFormError(null);
    setPending(true);
    try {
      await register(parsed.data);
      router.replace("/exercise");
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Registration failed");
    } finally {
      setPending(false);
    }
  };

  const set = (k: keyof Values) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setValues((v) => ({ ...v, [k]: e.target.value }));

  return (
    <div className="flex min-h-screen items-center justify-center px-4">
      <div className="w-full max-w-sm rounded-xl border border-line bg-panel p-6">
        <Logo subtitle className="mb-6" />
        <h1 className="text-base font-semibold">Create a trainee account</h1>
        <p className="mb-5 mt-1 text-xs text-muted">Instructor access is granted by a platform administrator.</p>
        <form onSubmit={submit} noValidate className="space-y-4">
          <Field label="Name" htmlFor="reg-name" error={errors.display_name}>
            <Input id="reg-name" value={values.display_name} onChange={set("display_name")} autoComplete="name" />
          </Field>
          <Field label="Email" htmlFor="reg-email" error={errors.email}>
            <Input id="reg-email" type="email" value={values.email} onChange={set("email")} autoComplete="email" />
          </Field>
          <Field label="Password" htmlFor="reg-password" error={errors.password} hint="8+ characters with letters and numbers">
            <Input
              id="reg-password"
              type="password"
              value={values.password}
              onChange={set("password")}
              autoComplete="new-password"
            />
          </Field>
          {formError && (
            <p role="alert" className="rounded-md border border-crit/40 bg-crit-soft px-3 py-2 text-sm text-crit">
              {formError}
            </p>
          )}
          <Button type="submit" variant="primary" className="w-full" loading={pending}>
            <UserPlus aria-hidden /> Create account
          </Button>
        </form>
        <p className="mt-4 text-center text-xs text-muted">
          Already registered?{" "}
          <Link href="/login" className="text-accent hover:underline">
            Sign in
          </Link>
        </p>
      </div>
    </div>
  );
}
