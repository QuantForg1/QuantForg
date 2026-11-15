"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Suspense,
  useCallback,
  useEffect,
  useRef,
  useState,
  type ClipboardEvent,
  type KeyboardEvent,
} from "react";
import { toast } from "sonner";
import { AuthShell } from "@/components/auth/auth-shell";
import { Button } from "@/components/ui/button";
import { authApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import {
  clearPendingVerifyEmail,
  getPendingVerifyEmail,
  saveSession,
  setPendingVerifyEmail,
  type AuthSession,
} from "@/lib/auth/session";
import { useAuth } from "@/providers/auth-provider";
import { cn } from "@/lib/utils";

const OTP_LEN = 6;
const RESEND_COOLDOWN_S = 60;

function maskEmail(email: string): string {
  const [local, domain] = email.split("@");
  if (!local || !domain) return email;
  if (local.length <= 2) return `${local[0] || "*"}***@${domain}`;
  return `${local.slice(0, 2)}***@${domain}`;
}

function mapVerifyError(err: unknown): string {
  if (!(err instanceof ApiError)) {
    return err instanceof Error ? err.message : "Verification failed";
  }
  const code = (err.code || "").toLowerCase();
  if (code.includes("expired") || err.message.toLowerCase().includes("expired")) {
    return "This code has expired. Request a new one.";
  }
  if (code.includes("rate") || err.status === 429) {
    return "Too many attempts. Wait a moment and try again.";
  }
  if (
    code.includes("otp") ||
    code.includes("token") ||
    code.includes("invalid") ||
    err.status === 400 ||
    err.status === 401
  ) {
    return "Invalid verification code. Check the digits and try again.";
  }
  return err.message || "Verification failed";
}

function OtpInputs({
  value,
  onChange,
  disabled,
}: {
  value: string[];
  onChange: (next: string[]) => void;
  disabled?: boolean;
}) {
  const refs = useRef<Array<HTMLInputElement | null>>([]);

  const focusAt = (index: number) => {
    const el = refs.current[index];
    if (el) {
      el.focus();
      el.select();
    }
  };

  const setDigit = (index: number, digit: string) => {
    const next = [...value];
    next[index] = digit;
    onChange(next);
    if (digit && index < OTP_LEN - 1) focusAt(index + 1);
  };

  const onKeyDown = (index: number, e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Backspace") {
      e.preventDefault();
      if (value[index]) {
        setDigit(index, "");
        return;
      }
      if (index > 0) {
        setDigit(index - 1, "");
        focusAt(index - 1);
      }
      return;
    }
    if (e.key === "ArrowLeft" && index > 0) {
      e.preventDefault();
      focusAt(index - 1);
    }
    if (e.key === "ArrowRight" && index < OTP_LEN - 1) {
      e.preventDefault();
      focusAt(index + 1);
    }
  };

  const onPaste = (e: ClipboardEvent<HTMLInputElement>) => {
    e.preventDefault();
    const text = e.clipboardData.getData("text").replace(/\D/g, "").slice(0, OTP_LEN);
    if (!text) return;
    const next = Array.from({ length: OTP_LEN }, (_, i) => text[i] || "");
    onChange(next);
    focusAt(Math.min(text.length, OTP_LEN - 1));
  };

  return (
    <div className="flex justify-center gap-2 sm:gap-2.5" role="group" aria-label="Six-digit verification code">
      {value.map((digit, index) => (
        <input
          key={index}
          ref={(el) => {
            refs.current[index] = el;
          }}
          id={index === 0 ? "otp-0" : undefined}
          type="text"
          inputMode="numeric"
          autoComplete={index === 0 ? "one-time-code" : "off"}
          pattern="[0-9]*"
          maxLength={1}
          aria-label={`Digit ${index + 1}`}
          disabled={disabled}
          value={digit}
          className={cn(
            "h-12 w-10 rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] text-center font-mono text-lg font-semibold text-[var(--fg)] outline-none transition",
            "focus:border-[var(--accent)] focus:ring-2 focus:ring-[var(--accent-soft)]",
            "disabled:opacity-60 sm:h-14 sm:w-11",
          )}
          onChange={(e) => {
            const raw = e.target.value.replace(/\D/g, "");
            if (!raw) {
              setDigit(index, "");
              return;
            }
            if (raw.length > 1) {
              const chars = raw.slice(0, OTP_LEN - index).split("");
              const next = [...value];
              chars.forEach((ch, offset) => {
                next[index + offset] = ch;
              });
              onChange(next);
              focusAt(Math.min(index + chars.length, OTP_LEN - 1));
              return;
            }
            setDigit(index, raw);
          }}
          onKeyDown={(e) => onKeyDown(index, e)}
          onPaste={onPaste}
          onFocus={(e) => e.target.select()}
        />
      ))}
    </div>
  );
}

function VerifyForm() {
  const params = useSearchParams();
  const router = useRouter();
  const { refreshMe } = useAuth();
  const emailParam = params.get("email") || "";
  const [email, setEmail] = useState(
    () => emailParam || getPendingVerifyEmail() || "",
  );
  const [digits, setDigits] = useState<string[]>(() => Array(OTP_LEN).fill(""));
  const [submitting, setSubmitting] = useState(false);
  const [resending, setResending] = useState(false);
  const [cooldown, setCooldown] = useState(0);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const inFlight = useRef(false);

  useEffect(() => {
    if (emailParam) setPendingVerifyEmail(emailParam);
  }, [emailParam]);

  useEffect(() => {
    if (cooldown <= 0) return;
    const id = window.setInterval(() => {
      setCooldown((c) => Math.max(0, c - 1));
    }, 1000);
    return () => window.clearInterval(id);
  }, [cooldown]);

  const code = digits.join("");
  const ready = Boolean(email.trim()) && code.length === OTP_LEN && /^\d{6}$/.test(code);

  const complete = useCallback(
    async (session: AuthSession) => {
      saveSession(session, { remember: true });
      clearPendingVerifyEmail();
      setSuccess(true);
      toast.success("Email verified");
      try {
        await refreshMe();
      } catch {
        /* session already saved */
      }
      router.replace("/dashboard");
    },
    [refreshMe, router],
  );

  const onVerify = async () => {
    if (!ready || inFlight.current) return;
    inFlight.current = true;
    setSubmitting(true);
    setError(null);
    try {
      const result = await authApi.verifyEmail({
        email: email.trim().toLowerCase(),
        token: code,
        type: "email",
      });
      if (result && typeof result === "object" && "access_token" in result) {
        await complete(result as AuthSession);
        return;
      }
      toast.success("Email verified — sign in to continue");
      clearPendingVerifyEmail();
      router.replace("/login");
    } catch (err) {
      const message = mapVerifyError(err);
      setError(message);
      toast.error(message);
    } finally {
      inFlight.current = false;
      setSubmitting(false);
    }
  };

  const onResend = async () => {
    if (!email.trim() || cooldown > 0 || resending) return;
    setResending(true);
    setError(null);
    try {
      const result = await authApi.resendVerification(email.trim().toLowerCase());
      toast.success(result.message || "If verification is needed, a new code was sent.");
      setCooldown(RESEND_COOLDOWN_S);
      setDigits(Array(OTP_LEN).fill(""));
    } catch (err) {
      if (err instanceof ApiError && err.status === 429) {
        setError("Too many requests. Please wait before requesting another code.");
        setCooldown(RESEND_COOLDOWN_S);
      } else {
        // Anti-enumeration: still show generic success-ish message
        toast.success("If verification is needed, a new code was sent.");
        setCooldown(RESEND_COOLDOWN_S);
      }
    } finally {
      setResending(false);
    }
  };

  return (
    <div className="space-y-5">
      {!email ? (
        <div className="space-y-2">
          <label htmlFor="verify-email" className="text-sm font-medium text-[var(--fg)]">
            Email address
          </label>
          <input
            id="verify-email"
            type="email"
            autoComplete="email"
            className="h-11 w-full rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-3 text-sm outline-none focus:border-[var(--accent)]"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="you@firm.com"
          />
        </div>
      ) : (
        <p className="text-center text-sm text-[var(--fg-muted)]">
          We sent a six-digit code to{" "}
          <span className="font-medium text-[var(--fg)]">{maskEmail(email)}</span>
        </p>
      )}

      <OtpInputs value={digits} onChange={setDigits} disabled={submitting || success} />

      {error ? (
        <p className="text-center text-sm text-[var(--danger)]" role="alert">
          {error}
        </p>
      ) : null}
      {success ? (
        <p className="text-center text-sm text-[var(--success)]" role="status">
          Verified. Opening Overview…
        </p>
      ) : null}

      <Button
        className="qf-btn-hot h-11 w-full"
        type="button"
        disabled={!ready || submitting || success}
        onClick={() => void onVerify()}
      >
        {submitting ? "Verifying…" : success ? "Verified" : "Verify email"}
      </Button>

      <div className="flex flex-col items-center gap-2 text-sm text-[var(--fg-muted)]">
        <button
          type="button"
          className="text-[var(--accent)] disabled:opacity-50"
          disabled={!email.trim() || cooldown > 0 || resending || success}
          onClick={() => void onResend()}
        >
          {resending
            ? "Sending…"
            : cooldown > 0
              ? `Resend code in ${cooldown}s`
              : "Resend code"}
        </button>
        <Link href="/login" className="text-[var(--accent)]">
          Back to sign in
        </Link>
      </div>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <AuthShell
      title="Verify your email"
      subtitle="Enter the six-digit code from your QuantForg verification email."
    >
      <Suspense fallback={<p className="text-sm text-[var(--fg-muted)]">Loading…</p>}>
        <VerifyForm />
      </Suspense>
    </AuthShell>
  );
}
