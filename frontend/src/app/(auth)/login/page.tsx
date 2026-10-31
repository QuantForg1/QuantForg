"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Eye, EyeOff, Lock, Mail } from "lucide-react";
import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleAuthNote } from "@/components/auth/google-auth-note";
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
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "", remember: true },
  });

  return (
    <AuthShell
      title="Welcome Back"
      subtitle="Sign in to your QuantForg account and continue with the desk you already use."
    >
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            await login(values.email, values.password, {
              remember: values.remember !== false,
            });
            toast.success("Signed in");
            router.replace("/dashboard");
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
          <Label htmlFor="password">Password</Label>
          <div className="relative">
            <Lock
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
              aria-hidden
            />
            <Input
              id="password"
              type={showPassword ? "text" : "password"}
              autoComplete="current-password"
              placeholder="••••••••"
              className="px-9"
              {...form.register("password")}
            />
            <button
              type="button"
              className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--fg-subtle)]"
              aria-label={showPassword ? "Hide password" : "Show password"}
              onClick={() => setShowPassword((value) => !value)}
            >
              {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </div>
        <div className="flex items-center justify-between gap-2">
          <label className="flex items-center gap-2 text-sm text-[var(--fg-muted)]">
            <input
              type="checkbox"
              className="h-4 w-4 accent-[var(--accent)]"
              {...form.register("remember")}
            />
            Remember me
          </label>
          <Link href="/forgot-password" className="text-sm text-[var(--accent)]">
            Forgot password
          </Link>
        </div>
        <Button className="qf-btn-hot h-11 w-full" type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Signing in…" : "Sign In"}
        </Button>
      </form>
      <GoogleAuthNote />
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-medium text-[var(--accent)]">
          Create account
        </Link>
      </p>
    </AuthShell>
  );
}
