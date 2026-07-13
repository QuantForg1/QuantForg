"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
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

const schema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

export default function LoginPage() {
  const { login } = useAuth();
  const router = useRouter();
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: { email: "", password: "" },
  });

  return (
    <AuthShell title="Welcome back" subtitle="Sign in to your QuantForg workspace.">
      <form
        className="space-y-4"
        onSubmit={form.handleSubmit(async (values) => {
          try {
            await login(values.email, values.password);
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
          <Input id="email" type="email" autoComplete="email" {...form.register("email")} />
        </div>
        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label htmlFor="password">Password</Label>
            <Link href="/forgot-password" className="text-xs text-[var(--accent)]">
              Forgot password?
            </Link>
          </div>
          <Input
            id="password"
            type="password"
            autoComplete="current-password"
            {...form.register("password")}
          />
        </div>
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
