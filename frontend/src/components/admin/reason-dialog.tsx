"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "@/components/ui/dialog";

/** Confirmation that requires a written reason (stored in the audit log). */
export function ReasonDialog({
  open,
  title,
  body,
  confirmLabel,
  danger,
  pending,
  onCancel,
  onConfirm,
}: {
  open: boolean;
  title: string;
  body: string;
  confirmLabel: string;
  danger?: boolean;
  pending?: boolean;
  onCancel: () => void;
  onConfirm: (reason: string) => void;
}) {
  const [reason, setReason] = useState("");
  const valid = reason.trim().length >= 3;
  return (
    <Dialog
      open={open}
      onOpenChange={(o) => {
        if (!o) {
          setReason("");
          onCancel();
        }
      }}
    >
      <DialogContent className="w-[min(94vw,460px)]">
        <form
          className="space-y-3"
          onSubmit={(e) => {
            e.preventDefault();
            if (valid && !pending) onConfirm(reason.trim());
          }}
        >
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{body}</DialogDescription>
          <label className="block space-y-1 text-sm">
            <span className="text-[var(--fg-muted)]">Reason (saved in the audit log)</span>
            <textarea
              value={reason}
              onChange={(e) => setReason(e.target.value)}
              rows={3}
              maxLength={500}
              autoFocus
              className="w-full rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
              placeholder="e.g. Customer asked to close the account"
            />
          </label>
          <div className="flex justify-end gap-2">
            <Button
              type="button"
              variant="ghost"
              onClick={() => {
                setReason("");
                onCancel();
              }}
            >
              Cancel
            </Button>
            <Button type="submit" variant={danger ? "danger" : "default"} disabled={!valid || pending}>
              {pending ? "Saving…" : confirmLabel}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
