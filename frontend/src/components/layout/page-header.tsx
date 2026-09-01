import type { ReactNode } from "react";

export function PageHeader({
  title,
  description,
  eyebrow,
  actions,
}: {
  title: string;
  description?: string;
  eyebrow?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="mb-[var(--space-5)] flex flex-col gap-[var(--space-3)] sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        {eyebrow ? (
          <p className="mb-1 text-[11px] font-semibold uppercase tracking-[0.16em] text-[var(--fg-subtle)]">
            {eyebrow}
          </p>
        ) : null}
        <h1 className="text-[1.5rem] font-semibold leading-tight tracking-tight text-[var(--fg)] sm:text-[var(--text-title)] sm:leading-[var(--leading-title)]">
          {title}
        </h1>
        {description ? (
          <p className="mt-1.5 max-w-2xl text-sm leading-relaxed text-[var(--fg-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
