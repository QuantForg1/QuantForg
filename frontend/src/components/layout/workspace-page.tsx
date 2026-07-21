import type { LucideIcon } from "lucide-react";
import type { ReactNode } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { DeskEmpty } from "@/components/desk/primitives";

/**
 * Focused workspace page chrome — one responsibility, elegant empty when live data absent.
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
    <div className="space-y-6">
      <PageHeader title={title} description={description} actions={actions} />
      {children ?? (
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
      )}
    </div>
  );
}
