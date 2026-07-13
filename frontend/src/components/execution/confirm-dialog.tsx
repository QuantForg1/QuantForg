"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  tone = "default",
  busy,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  tone?: "default" | "danger";
  busy?: boolean;
  onConfirm: () => void | Promise<void>;
}) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(96vw,440px)]" aria-describedby="confirm-desc">
        <DialogTitle className="pr-10">{title}</DialogTitle>
        <p id="confirm-desc" className="mt-2 text-sm text-[var(--fg-muted)]">
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="secondary" disabled={busy}>
              Cancel
            </Button>
          </DialogClose>
          <Button
            variant={tone === "danger" ? "danger" : "default"}
            disabled={busy}
            onClick={() => {
              void (async () => {
                try {
                  await onConfirm();
                } catch {
                  /* callers toast their own failures; prevent unhandled rejection */
                }
              })();
            }}
            aria-label={confirmLabel}
          >
            {busy ? "Working…" : confirmLabel}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
