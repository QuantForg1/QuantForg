"use client";

import { memo, type ReactNode } from "react";
import { cn } from "@/lib/utils";

/**
 * Shared inline empty state for OS desk panels (Terminal / Book / Research / Counsel).
 * Never invent data — calm honesty only.
 */
export const DeskInlineEmpty = memo(function DeskInlineEmpty({
  title,
  description,
  className,
  action,
  minHeight = "5rem",
}: {
  title: string;
  description?: string;
  className?: string;
  action?: ReactNode;
  minHeight?: string;
}) {
  return (
    <div
      className={cn(
        "flex h-full flex-col items-center justify-center gap-2 px-4 text-center",
        className,
      )}
      style={{ minHeight }}
      role="status"
    >
      <p className="qf-heading text-[var(--fg)]">{title}</p>
      {description ? (
        <p className="qf-caption max-w-sm text-[var(--fg-muted)]">{description}</p>
      ) : null}
      {action}
    </div>
  );
});
