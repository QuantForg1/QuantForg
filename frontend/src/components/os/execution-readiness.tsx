"use client";

/**
 * Execution Readiness — institutional pre-trade surface.
 * Renders only from live session + ticket state. Never invents readiness.
 */

import { cn } from "@/lib/utils";

export type ReadinessCheck = {
  id: string;
  label: string;
  ok: boolean | null;
  detail?: string;
};

export function ExecutionReadiness({
  checks,
  className,
}: {
  checks: ReadinessCheck[];
  className?: string;
}) {
  if (!checks.length) {
    return (
      <div
        className={cn(
          "rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 py-4 text-center",
          className,
        )}
      >
        <p className="qf-heading text-[var(--fg)]">Execution readiness</p>
        <p className="qf-caption mt-1">
          Open a ticket with a live session to evaluate readiness.
        </p>
      </div>
    );
  }

  const known = checks.filter((c) => c.ok !== null);
  const ready = known.length > 0 && known.every((c) => c.ok === true);
  const blocked = known.some((c) => c.ok === false);

  return (
    <section
      className={cn(
        "rounded-md border border-[var(--border)] bg-[var(--surface)] p-3",
        className,
      )}
      aria-label="Execution readiness"
    >
      <header className="mb-2 flex items-baseline justify-between gap-2">
        <h2 className="qf-label text-[var(--fg)]">Execution readiness</h2>
        <span
          className={cn(
            "qf-caption tabular",
            ready && "text-[var(--success)]",
            blocked && "text-[var(--danger)]",
            !ready && !blocked && "text-[var(--fg-muted)]",
          )}
        >
          {ready ? "Ready" : blocked ? "Blocked" : "Pending"}
        </span>
      </header>
      <ul className="space-y-1.5">
        {checks.map((c) => (
          <li
            key={c.id}
            className="flex items-start justify-between gap-3 text-[var(--text-caption)]"
          >
            <span className="text-[var(--fg-muted)]">{c.label}</span>
            <span
              className={cn(
                "shrink-0 tabular",
                c.ok === true && "text-[var(--success)]",
                c.ok === false && "text-[var(--danger)]",
                c.ok === null && "text-[var(--fg-subtle)]",
              )}
            >
              {c.ok === true ? "Pass" : c.ok === false ? "Fail" : "—"}
            </span>
          </li>
        ))}
      </ul>
    </section>
  );
}
