import type { ReactNode } from "react";
import { AlertTriangle, RefreshCw } from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { EmptyState } from "@/components/ui/empty-state";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export function DeskSkeleton({
  rows = 3,
  variant = "list",
}: {
  rows?: number;
  variant?: "list" | "kpis" | "chart" | "page";
}) {
  if (variant === "kpis") {
    return (
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4" aria-busy="true" aria-label="Loading metrics">
        {Array.from({ length: rows }).map((_, i) => (
          <Card key={i}>
            <CardHeader>
              <Skeleton className="h-3 w-20" />
            </CardHeader>
            <CardContent>
              <Skeleton className="h-8 w-28" />
              <Skeleton className="mt-2 h-3 w-16" />
            </CardContent>
          </Card>
        ))}
      </div>
    );
  }

  if (variant === "chart") {
    return (
      <Card aria-busy="true" aria-label="Loading chart">
        <CardHeader>
          <Skeleton className="h-4 w-32" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-64 w-full" />
        </CardContent>
      </Card>
    );
  }

  if (variant === "page") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading page">
        <DeskSkeleton variant="kpis" rows={4} />
        <div className="grid gap-4 xl:grid-cols-2">
          <DeskSkeleton variant="chart" />
          <DeskSkeleton rows={4} />
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-3" aria-busy="true" aria-label="Loading">
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className="h-14 w-full" />
      ))}
    </div>
  );
}

export function DeskError({
  message = "Unable to load this resource.",
  onRetry,
}: {
  message?: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="flex flex-col items-start gap-3 rounded-xl border border-[var(--danger)]/30 bg-[var(--danger-soft)] p-4 sm:flex-row sm:items-center sm:justify-between"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-[var(--danger)]" aria-hidden />
        <p className="text-sm text-[var(--fg)]">{message}</p>
      </div>
      {onRetry ? (
        <Button variant="secondary" size="sm" onClick={onRetry} aria-label="Retry loading">
          <RefreshCw className="h-3.5 w-3.5" />
          Retry
        </Button>
      ) : null}
    </div>
  );
}

export function DeskEmpty({
  icon,
  title,
  description,
  actionLabel,
  onAction,
  secondaryLabel,
  onSecondary,
}: {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
}) {
  return (
    <EmptyState
      icon={icon}
      title={title}
      description={description}
      actionLabel={actionLabel}
      onAction={onAction}
      secondaryLabel={secondaryLabel}
      onSecondary={onSecondary}
    />
  );
}

export function DeskTable({
  columns,
  rows,
}: {
  columns: string[];
  rows: ReactNode[][];
}) {
  return (
    <div className="overflow-x-auto rounded-lg border border-[var(--border)]">
      <table className="w-full text-left text-sm">
        <thead className="sticky top-0 bg-[var(--surface-2)]/95 text-[var(--fg-subtle)] backdrop-blur">
          <tr>
            {columns.map((c) => (
              <th key={c} className="px-3 py-2.5 text-xs font-medium uppercase tracking-wide">
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr
              key={i}
              className="border-t border-[var(--border)] transition-colors hover:bg-[var(--surface-2)]/60"
            >
              {row.map((cell, j) => (
                <td key={j} className="px-3 py-2.5 align-middle">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
