import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
  status,
}: {
  title: string;
  description?: string;
  eyebrow?: string;
  actions?: ReactNode;
  /** Optional status chip / live badge row under the title. */
  status?: ReactNode;
}) {
  return (
    <div className="mb-[var(--space-5)] flex flex-col gap-[var(--space-3)] lg:flex-row lg:items-start lg:justify-between">
      <div className="min-w-0 flex-1">
        {eyebrow ? (
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--accent)]">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-[1.35rem] font-semibold leading-tight tracking-tight text-[var(--fg)] sm:text-[1.85rem] sm:leading-[var(--leading-title)]">
          {title}
        </h1>
        {description ? (
          <p className="mt-1.5 max-w-3xl text-sm leading-relaxed text-[var(--fg-muted)]">
            {description}
          </p>
        ) : null}
        {status ? (
          <div className="mt-2.5 flex flex-wrap items-center gap-2">{status}</div>
        ) : null}
      </div>
      {actions ? (
        <div className="flex w-full min-w-0 shrink-0 flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:items-center">
          {actions}
        </div>
      ) : null}
    </div>
  );
}
