"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Lock, Mail } from "lucide-react";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/providers/auth-provider";
import { ApiError } from "@/lib/api/client";

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
  remember: z.boolean(),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", remember: true },
  });

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your QuantForg workspace.">
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            await login(values.email, values.password, {
              remember: values.remember !== false,
            });
            toast.success("Signed in");
            router.replace("/terminal");
          } catch (e) {
            if (e instanceof ApiError && e.code === "email_not_verified") {
              toast.error("Verify your email before signing in.");
              router.push("/verify-email");
              return;
            }
            toast.error(
              e instanceof ApiError
                ? e.message
                : e instanceof Error
                  ? e.message
                  : "Login failed",
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
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-xs text-[var(--accent)]">
              Forgot password?
            </Link>
          </div>
          <div className="relative">
            <Lock
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
              aria-hidden
            />
            <Input
              id="password"
              type="password"
              autoComplete="current-password"
              placeholder="••••••••"
              className="pl-9"
              {...form.register("password")}
            />
          </div>
        </div>
        <label className="flex items-center gap-2 text-sm text-[var(--fg-muted)]">
          <input
            type="checkbox"
            className="h-4 w-4 accent-[var(--accent)]"
            {...form.register("remember")}
          />
          Remember me
        </label>
        <Button className="w-full" type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Signing in…" : "Sign in"}
        </Button>
      </form>
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        No account?{" "}
        <Link href="/register" className="text-[var(--accent)]">
          Create one
        </Link>
      </p>
    </AuthShell>
  );
}
