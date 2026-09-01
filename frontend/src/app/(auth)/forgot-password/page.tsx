"use client";

import Link from "next/link";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Mail } from "lucide-react";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

const schema = z.object({
  email: z.string().email("Enter a valid email"),
});

type FormValues = z.infer<typeof schema>;

export default function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  return (
    <AuthShell
      title="Reset your password"
      subtitle="Enter your email and we will send a reset link if an account exists."
    >
      {sent ? (
        <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
          If an account exists for that email, a reset link has been sent. Check your inbox
          and follow the link to choose a new password.
        </p>
      ) : (
        <form
          className="space-y-4"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              const redirect =
                typeof window !== "undefined"
                  ? `${window.location.origin}/reset-password`
                  : undefined;
              const result = await authApi.forgotPassword(values.email, redirect);
              setSent(true);
              toast.success(result.message || "Reset email sent");
            } catch (e) {
              toast.error(
                e instanceof ApiError
                  ? e.message
                  : e instanceof Error
                    ? e.message
                    : "Could not send reset email",
              );
            }
          })}
        >
          <div className="space-y-2">
            <Label htmlFor="email">Email</Label>
            <div className="relative">
              <Mail
                className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
                aria-hidden
              />
              <Input
                id="email"
                type="email"
                autoComplete="email"
                placeholder="you@firm.com"
                className="pl-9"
                {...form.register("email")}
              />
            </div>
            {form.formState.errors.email ? (
              <p className="text-xs text-[var(--danger)]">
                {form.formState.errors.email.message}
              </p>
            ) : null}
          </div>
          <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
            {form.formState.isSubmitting ? "Sending…" : "Send reset link"}
          </Button>
        </form>
      )}
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        <Link href="/login" className="text-[var(--accent)]">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
