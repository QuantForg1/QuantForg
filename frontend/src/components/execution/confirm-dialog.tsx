"use client";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  EXECUTION_STAGE_LABEL,
  type ExecutionStageId,
} from "@/lib/execution/submit-errors";
import { cn } from "@/lib/utils";

const PIPELINE: ExecutionStageId[] = [
  "validating",
  "risk",
  "sending",
  "broker",
];

export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  confirmLabel = "Confirm",
  tone = "default",
  busy,
  stage = "idle",
  rejectReason,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  confirmLabel?: string;
  tone?: "default" | "danger";
  busy?: boolean;
  /** Live pipeline progress while submitting. */
  stage?: ExecutionStageId;
  rejectReason?: string;
  onConfirm: () => void | Promise<void>;
}) {
  const activeIdx = PIPELINE.indexOf(
    stage === "completed" || stage === "rejected" ? "broker" : stage,
  );
  const showProgress = busy || stage === "completed" || stage === "rejected";

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="w-[min(96vw,440px)]" aria-describedby="confirm-desc">
        <DialogTitle className="pr-10">{title}</DialogTitle>
        <p id="confirm-desc" className="mt-2 text-sm text-[var(--fg-muted)]">
          {description}
        </p>

        {showProgress ? (
          <ol className="mt-4 space-y-2" aria-live="polite" aria-busy={busy}>
            {PIPELINE.map((id, i) => {
              const done =
                stage === "completed" ||
                (activeIdx > i && stage !== "rejected") ||
                (stage === "rejected" && activeIdx > i);
              const current = stage === id || (stage === "rejected" && i === activeIdx);
              const failed = stage === "rejected" && current;
              return (
                <li
                  key={id}
                  className={cn(
                    "flex items-center gap-2 text-sm",
                    done && "text-[var(--success)]",
                    current && !failed && "text-[var(--accent)]",
                    failed && "text-[var(--danger)]",
                    !done && !current && "text-[var(--fg-subtle)]",
                  )}
                >
                  <span
                    className={cn(
                      "qf-status-dot",
                      done && "bg-[var(--success)]",
                      current && !failed && "bg-[var(--accent)]",
                      failed && "bg-[var(--danger)]",
                    )}
                    data-state={failed ? "err" : done ? "ok" : current ? "warn" : undefined}
                    aria-hidden
                  />
                  {EXECUTION_STAGE_LABEL[id]}
                </li>
              );
            })}
            {stage === "completed" ? (
              <li className="flex items-center gap-2 text-sm text-[var(--success)]">
                <span className="qf-status-dot" data-state="ok" aria-hidden />
                {EXECUTION_STAGE_LABEL.completed}
              </li>
            ) : null}
            {stage === "rejected" ? (
              <li className="space-y-1 text-sm text-[var(--danger)]">
                <div className="flex items-center gap-2">
                  <span className="qf-status-dot" data-state="err" aria-hidden />
                  {EXECUTION_STAGE_LABEL.rejected}
                </div>
                {rejectReason ? (
                  <p className="pl-4 text-[var(--fg-muted)]">{rejectReason}</p>
                ) : null}
              </li>
            ) : null}
          </ol>
        ) : null}

        <div className="mt-5 flex justify-end gap-2">
          <DialogClose asChild>
            <Button variant="secondary" disabled={busy}>
              {stage === "completed" || stage === "rejected" ? "Close" : "Cancel"}
            </Button>
          </DialogClose>
          {stage !== "completed" && stage !== "rejected" ? (
            <Button
              variant={tone === "danger" ? "danger" : "default"}
              disabled={busy}
              onClick={() => {
                void (async () => {
                  try {
                    await onConfirm();
                  } catch {
                    /* callers surface failures */
                  }
                })();
              }}
              aria-label={confirmLabel}
            >
              {busy ? EXECUTION_STAGE_LABEL[stage] || "Working…" : confirmLabel}
            </Button>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
