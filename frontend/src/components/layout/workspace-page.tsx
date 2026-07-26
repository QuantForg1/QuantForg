import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskEmpty } from "@/components/desk/primitives";
import { DESK_PANEL_SURFACE } from "@/components/desk/panel";
import { cn } from "@/lib/utils";

/**
 * Scrollable workspace page chrome — Phase 1 language for Settings / Ops / History / Labs.
 * One responsibility; elegant empty when live data absent.
 */
export function WorkspacePage({
  title,
  description,
  icon: Icon,
  emptyTitle,
  emptyDescription,
  actionLabel,
  actionHref,
  actions,
  children,
}: {
  title: string;
  description: string;
  icon: LucideIcon;
  emptyTitle?: string;
  emptyDescription?: string;
  actionLabel?: string;
  actionHref?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  return (
    <div className="space-y-[var(--space-5)]">
      <PageHeader title={title} description={description} actions={actions} />
      {children ?? (
        <div className={cn(DESK_PANEL_SURFACE, "p-[var(--space-5)]")}>
          <DeskEmpty
            icon={Icon}
            title={emptyTitle ?? title}
            description={
              emptyDescription ??
              "This workspace is ready. Live data appears when the session provides it."
            }
            actionLabel={actionLabel}
            actionHref={actionHref}
          />
        </div>
      )}
    </div>
  );
}
