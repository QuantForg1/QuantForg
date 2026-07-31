"use client";

import Link from "next/link";
import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/providers/auth-provider";
import { ApiError } from "@/lib/api/client";
import {
  hasLifetimePurchaseEntitlement,
  markLifetimePurchaseComplete,
} from "@/lib/licensing/purchase-gate";

const schema = z.object({
  display_name: z.string().min(1).max(120),
  email: z.string().email(),
  password: z.string().min(8).max(128),
});

type FormValues = z.infer<typeof schema>;

function RegisterForm() {
  const { register: registerUser } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [allowed, setAllowed] = useState<boolean | null>(null);

  useEffect(() => {
    const fromSuccess = searchParams.get("licensed") === "1";
    if (fromSuccess) {
      markLifetimePurchaseComplete();
      setAllowed(true);
      return;
    }
    setAllowed(hasLifetimePurchaseEntitlement());
  }, [searchParams]);

  useEffect(() => {
    if (allowed === false) {
      router.replace("/pricing");
    }
  }, [allowed, router]);

  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { display_name: "", email: "", password: "" },
  });

  if (allowed !== true) {
    return (
      <AuthShell title="Purchase required" subtitle="Redirecting to pricing…">
        <p className="text-center text-sm text-[var(--fg-muted)]">
          Create account is available only after a successful license purchase.
        </p>
        <Link
          href="/pricing"
          className="mt-4 inline-flex w-full items-center justify-center rounded-[var(--radius-sm)] qf-btn-primary h-11 text-sm font-medium"
        >
          View pricing
        </Link>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Create workspace"
      subtitle="License confirmed. Register with email to access the terminal."
    >
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            const message = await registerUser(
              values.email,
              values.password,
              values.display_name,
            );
            if (message) {
              toast.success(message);
              router.push("/verify-email");
              return;
            }
            toast.success("Account created");
            router.replace("/terminal");
          } catch (e) {
            if (e instanceof ApiError && e.code === "auth_rate_limited") {
              toast.error("Too many attempts. Please wait a few minutes and try again.");
            } else {
              toast.error(
                e instanceof ApiError
                  ? e.message
                  : e instanceof Error
                    ? e.message
                    : "Registration failed",
              );
            }
          }
        })}
      >
        <div className="space-y-2">
          <Label htmlFor="display_name">Display name</Label>
          <Input id="display_name" {...form.register("display_name")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="email">Email</Label>
          <Input id="email" type="email" {...form.register("email")} />
        </div>
        <div className="space-y-2">
          <Label htmlFor="password">Password</Label>
          <Input id="password" type="password" {...form.register("password")} />
        </div>
        <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Creating…" : "Create account"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        Already registered?{" "}
        <Link href="/login" className="text-[var(--accent)]">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense
      fallback={
        <AuthShell title="Create workspace" subtitle="Loading…">
          <div className="h-40 animate-pulse rounded-lg bg-[var(--surface-2)]" />
        </AuthShell>
      }
    >
      <RegisterForm />
    </Suspense>
  );
}
