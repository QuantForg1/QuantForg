import Link from "next/link";
import { AuthShell } from "@/components/auth/auth-shell";

/** Self-serve password reset UI removed — operators contact QuantForg Support. */
export default function ResetPasswordPage() {
  return (
    <AuthShell
      title="Need help accessing your account?"
      subtitle="Password changes are handled by QuantForg Support."
    >
      <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
        Self-service password reset is not available. Contact QuantForg Support to restore access
        to your workspace.
      </p>
      <Link
        href="/contact"
        className="mt-6 inline-flex h-11 w-full items-center justify-center rounded-[var(--radius-sm)] qf-btn-primary text-sm font-medium"
      >
        Contact QuantForg Support
      </Link>
      <p className="mt-4 text-center text-sm text-[var(--fg-muted)]">
        <Link href="/login" className="text-[var(--accent)]">
          Back to sign in
        </Link>
      </p>
    </AuthShell>
  );
}
