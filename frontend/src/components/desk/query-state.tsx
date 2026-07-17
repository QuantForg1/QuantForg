import type { ReactNode } from "react";
import type { LucideIcon } from "lucide-react";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";

export type DeskQueryEmpty = {
  icon: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
  actionHref?: string;
  secondaryLabel?: string;
  onSecondary?: () => void;
  secondaryHref?: string;
};

type SkeletonVariant = "list" | "kpis" | "chart" | "page";

/**
 * Single reusable async boundary for desk pages:
 * loading → error → optional empty → content.
 */
export function DeskQueryState({
  isLoading,
  isError,
  isEmpty = false,
  errorMessage = "Unable to load this resource.",
  onRetry,
  skeleton = "page",
  skeletonRows,
  empty,
  children,
}: {
  isLoading: boolean;
  isError: boolean;
  /** When true (and not loading/error), renders `empty` instead of children. */
  isEmpty?: boolean;
  errorMessage?: string;
  onRetry?: () => void;
  skeleton?: SkeletonVariant;
  skeletonRows?: number;
  empty?: DeskQueryEmpty;
  children: ReactNode;
}) {
  if (isLoading) {
    return (
      <DeskSkeleton
        variant={skeleton}
        rows={skeletonRows ?? (skeleton === "page" ? 4 : 3)}
      />
    );
  }

  if (isError) {
    return <DeskError message={errorMessage} onRetry={onRetry} />;
  }

  if (isEmpty && empty) {
    return <DeskEmpty {...empty} />;
  }

  return <>{children}</>;
}
