import Link from "next/link";
import { type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function EmptyState({
  icon: Icon,
  title,
  description,
  actionLabel,
  onAction,
  actionHref,
  secondaryLabel,
  onSecondary,
  secondaryHref,
  className,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  /** Prefer over onAction for in-app navigation (client-side, no full reload). */
  actionHref?: string;
  secondaryLabel?: string;
  onSecondary?: () => void;
  secondaryHref?: string;
  className?: string;
}) {
  const hasPrimary = Boolean(actionLabel && (actionHref || onAction));
  const hasSecondary = Boolean(secondaryLabel && (secondaryHref || onSecondary));

  return (
    <div
      role="status"
      className={cn(
          "flex flex-col items-center justify-center rounded-[var(--radius-os)] border border-dashed border-[var(--border)] bg-[var(--surface)] px-[var(--space-5)] py-[var(--space-7)] text-center qf-motion-desk",
        className,
      )}
    >
      <div
        className="mb-[var(--space-3)] flex h-12 w-12 items-center justify-center rounded-[var(--radius-os)] bg-[var(--accent-soft)] text-[var(--accent)]"
        aria-hidden
      >
        <Icon className="h-5 w-5" />
      </div>
      <h3 className="text-[var(--text-heading)] font-semibold leading-[var(--leading-heading)] tracking-tight text-[var(--fg)]">
        {title}
      </h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-[var(--fg-muted)]">
        {description}
      </p>
      {hasPrimary || hasSecondary ? (
        <div className="mt-[var(--space-5)] flex flex-wrap items-center justify-center gap-2">
          {hasPrimary ? (
            actionHref ? (
              <Button asChild>
                <Link href={actionHref}>{actionLabel}</Link>
              </Button>
            ) : (
              <Button onClick={onAction}>{actionLabel}</Button>
            )
          ) : null}
          {hasSecondary ? (
            secondaryHref ? (
              <Button variant="secondary" asChild>
                <Link href={secondaryHref}>{secondaryLabel}</Link>
              </Button>
            ) : (
              <Button variant="secondary" onClick={onSecondary}>
                {secondaryLabel}
              </Button>
            )
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
