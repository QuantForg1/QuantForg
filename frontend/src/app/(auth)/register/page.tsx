"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Eye, EyeOff, Lock, Mail, User } from "lucide-react";
import { AuthShell } from "@/components/auth/auth-shell";
import { GoogleAuthNote } from "@/components/auth/google-auth-note";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/providers/auth-provider";
import { ApiError } from "@/lib/api/client";

const schema = z
  .object({
    display_name: z.string().trim().min(1, "Enter your name").max(120),
    email: z.string().email("Enter a valid email"),
    password: z.string().min(8, "Password must be at least 8 characters"),
    confirm: z.string().min(1, "Confirm your password"),
    accepted: z.boolean().refine((value) => value, {
      message: "Accept the terms and privacy policy to create an account",
    }),
  })
  .refine((values) => values.password === values.confirm, {
    path: ["confirm"],
    message: "Passwords do not match",
  });

type FormValues = z.infer<typeof schema>;

export default function RegisterPage() {
  const { register: registerAccount } = useAuth();
  const router = useRouter();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { display_name: "", email: "", password: "", confirm: "", accepted: false },
  });
  const [showPassword, setShowPassword] = useState(false);

  return (
    <AuthShell
      title="Create your account"
      subtitle="Create your QuantForg account. A broker connection is required only when you are ready to trade."
    >
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            const pending = await registerAccount(
              values.email,
              values.password,
              values.display_name,
            );
            if (typeof pending === "string" && pending) {
              toast.success(pending);
              router.replace("/verify-email");
              return;
            }
            toast.success("Account created");
            router.replace("/get-started");
          } catch (e) {
            toast.error(
              e instanceof ApiError
                ? e.message
                : e instanceof Error
                  ? e.message
                  : "Registration failed",
            );
          }
        })}
      >
        <div className="space-y-2">
          <Label htmlFor="display_name">Full name</Label>
          <div className="relative">
            <User
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
              aria-hidden
            />
            <Input
              id="display_name"
              autoComplete="name"
              placeholder="Alex Rivera"
              className="pl-9"
              {...form.register("display_name")}
            />
          </div>
          {form.formState.errors.display_name ? (
            <p className="text-xs text-[var(--danger)]">
              {form.formState.errors.display_name.message}
            </p>
          ) : null}
        </div>
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
              autoComplete="new-password"
              placeholder="At least 8 characters"
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
          {form.formState.errors.password ? (
            <p className="text-xs text-[var(--danger)]">
              {form.formState.errors.password.message}
            </p>
          ) : null}
        </div>
        <div className="space-y-2">
          <Label htmlFor="confirm">Confirm password</Label>
          <div className="relative">
            <Lock
              className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-[var(--fg-subtle)]"
              aria-hidden
            />
            <Input
              id="confirm"
              type="password"
              autoComplete="new-password"
              placeholder="Repeat password"
              className="pl-9"
              {...form.register("confirm")}
            />
          </div>
          {form.formState.errors.confirm ? (
            <p className="text-xs text-[var(--danger)]">
              {form.formState.errors.confirm.message}
            </p>
          ) : null}
        </div>
        <label className="flex items-start gap-2 text-sm text-[var(--fg-muted)]">
          <input
            type="checkbox"
            className="mt-1 h-4 w-4 accent-[var(--hot)]"
            {...form.register("accepted")}
          />
          <span>
            I accept the{" "}
            <a className="text-[var(--accent)]" href="mailto:support@quantforg.com?subject=Terms%20of%20Service">
              Terms
            </a>{" "}
            and{" "}
            <a className="text-[var(--accent)]" href="mailto:support@quantforg.com?subject=Privacy%20Policy">
              Privacy Policy
            </a>
            .
          </span>
        </label>
        {form.formState.errors.accepted ? (
          <p className="text-xs text-[var(--danger)]">{form.formState.errors.accepted.message}</p>
        ) : null}
        <Button className="qf-btn-hot h-11 w-full" type="submit" disabled={form.formState.isSubmitting}>
          {form.formState.isSubmitting ? "Creating account…" : "Create Account"}
        </Button>
      </form>
      <GoogleAuthNote />
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        Already have an account?{" "}
        <Link href="/login" className="text-[var(--accent)]">
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
