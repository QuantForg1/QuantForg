"use client";

import { memo } from "react";
import { cn } from "@/lib/utils";

export const ResearchEmpty = memo(function ResearchEmpty({
  title,
  description,
  className,
  action,
}: {
  title: string;
  description?: string;
  className?: string;
  action?: React.ReactNode;
}) {
  return (
    <div
      className={cn(
        "flex h-full min-h-[5rem] flex-col items-center justify-center gap-2 px-4 text-center",
        className,
      )}
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
