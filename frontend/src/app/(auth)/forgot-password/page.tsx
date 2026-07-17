"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { authApi } from "@/lib/api/endpoints";
import { getClientAppOrigin } from "@/lib/env";
import { ApiError } from "@/lib/api/client";

const schema = z.object({ email: z.string().email() });

export default function ForgotPasswordPage() {
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { email: "" },
  });

  return (
    <AuthShell title="Reset password" subtitle="We will email a secure reset link if the account exists.">
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            await authApi.forgotPassword(
              values.email,
              `${getClientAppOrigin()}/reset-password`,
            );
            const { recordAudit } = await import("@/lib/observability/audit");
            recordAudit("password_reset", "success", "Password reset requested", {
              email: values.email,
            });
            toast.success("If the email exists, a reset link was sent.");
          } catch (e) {
            const { recordAudit } = await import("@/lib/observability/audit");
            recordAudit("password_reset", "failure", "Password reset request failed");
            toast.error(e instanceof ApiError ? e.message : "Request failed");
          }
        })}
      >
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" {...form.register("email")} />
        </div>
        <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
          Send reset link
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        <Link href="/login" className="text-[var(--accent)]">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
