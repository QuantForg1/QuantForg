import Link from "next/link";
import { AuthShell } from "@/components/auth/auth-shell";

/** Self-serve password recovery removed — operators contact QuantForg Support. */
export default function ForgotPasswordPage() {
  return (
    <AuthShell
      title="Need help accessing your account?"
      subtitle="Password resets are handled by QuantForg Support."
    >
      <p className="text-sm leading-relaxed text-[var(--fg-muted)]">
        QuantForg accounts are provisioned manually. If you cannot sign in, contact our team —
        we will verify your identity and restore access.
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
