"use client";

import { Dialog, DialogContent, DialogTitle } from "@/components/ui/dialog";

/**
 * Shared keyboard shortcuts dialog — Phase 1 OS desks.
 */
export function DeskShortcutsDialog({
  open,
  onOpenChange,
  title,
  shortcuts,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  shortcuts: { keys: string; action: string }[];
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-md">
        <DialogTitle>{title}</DialogTitle>
        <ul className="mt-3 space-y-2">
          {shortcuts.map((row) => (
            <li
              key={row.keys}
              className="flex items-baseline justify-between gap-4 text-sm"
            >
              <kbd className="rounded-[var(--radius-sm)] border border-[var(--border)] bg-[var(--surface-2)] px-1.5 py-0.5 font-mono text-[11px]">
                {row.keys}
              </kbd>
              <span className="text-[var(--fg-muted)]">{row.action}</span>
            </li>
          ))}
        </ul>
      </DialogContent>
    </Dialog>
  );
}
