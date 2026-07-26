export function PageHeader({
  title,
  description,
  actions,
}: {
  title: string;
  description?: string;
  actions?: React.ReactNode;
}) {
  return (
    <div className="mb-[var(--space-5)] flex flex-col gap-[var(--space-3)] sm:flex-row sm:items-end sm:justify-between">
      <div className="min-w-0">
        <h1 className="text-[var(--text-heading)] font-semibold leading-[var(--leading-heading)] tracking-tight text-[var(--fg)]">
          {title}
        </h1>
        {description ? (
          <p className="mt-1 max-w-2xl text-sm text-[var(--fg-muted)]">
            {description}
          </p>
        ) : null}
      </div>
      {actions ? (
        <div className="flex shrink-0 items-center gap-2">{actions}</div>
      ) : null}
    </div>
  );
}
