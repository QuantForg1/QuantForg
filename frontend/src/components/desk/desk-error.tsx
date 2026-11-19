"use client";

import { useEffect, useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { friendlyLoadMessage } from "@/lib/friendly-error";

/**
 * Calm, self-healing load state. Instead of a red "could not be loaded" box,
 * it says it is reconnecting and retries on its own (5 s, 10 s, 20 s … max
 * 60 s) while the user can still retry at once.
 */
export function DeskError({
  message = "Unable to load this resource.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  const [attempt, setAttempt] = useState(0);
  const retryRef = useRef(onRetry);
  useEffect(() => {
    retryRef.current = onRetry;
  }, [onRetry]);

  useEffect(() => {
    if (!retryRef.current) return;
    const delay = Math.min(60_000, 5_000 * 2 ** attempt);
    const t = window.setTimeout(() => {
      retryRef.current?.();
      setAttempt((a) => a + 1);
    }, delay);
    return () => window.clearTimeout(t);
  }, [attempt]);

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-start gap-3 rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface-2)] p-[var(--space-3)] sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-center gap-3">
        <span className="relative flex h-2.5 w-2.5 shrink-0" aria-hidden>
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--accent)] opacity-60" />
          <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-[var(--accent)]" />
        </span>
        <p className="text-sm text-[var(--fg-muted)]">{friendlyLoadMessage(message)}</p>
      </div>
      {onRetry ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            onRetry();
            setAttempt(0);
          }}
          aria-label="Retry now"
        >
          <RefreshCw className="h-3.5 w-3.5" />
          Retry now
        </Button>
      ) : null}
    </div>
  );
}
