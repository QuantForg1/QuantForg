"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  dismissTour,
  isTourDismissed,
  reopenTour,
  setChecklistItem,
} from "@/lib/platform/onboarding";

const STEPS = [
  {
    title: "Desk overview",
    body: "Dashboard and Intelligence summarize markets. Trading tools live under Workspace, Execution, and Paper.",
    href: "/dashboard",
  },
  {
    title: "Paper trading first",
    body: "Practice fills on /paper before connecting a live MT5 account. Live trading stays gated by EXECUTION_ENABLED.",
    href: "/paper",
  },
  {
    title: "Connect a broker",
    body: "Use the broker wizard on Get Started, then Compatibility and /mt5 with the exact portal server string.",
    href: "/get-started#broker",
  },
  {
    title: "Research & risk",
    body: "Strategy Builder, Risk Lab, and Execution Intelligence are analytics only — they never auto-trade.",
    href: "/risk-lab",
  },
  {
    title: "Send feedback",
    body: "Use the floating feedback control anytime. Beta operators triage bugs and feature requests weekly.",
    href: "/support#feedback",
  },
] as const;

type ProductTourProps = {
  forceOpen?: boolean;
  onClose?: () => void;
};

export function ProductTour({ forceOpen = false, onClose }: ProductTourProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setStep(0);
      return;
    }
    if (!isTourDismissed()) setOpen(true);
  }, [forceOpen]);

  function close(dismiss: boolean) {
    if (dismiss) dismissTour();
    setOpen(false);
    onClose?.();
  }

  const current = STEPS[step];

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) close(true);
      }}
    >
      <DialogContent className="max-w-md">
        <DialogTitle>
          Product tour · {step + 1}/{STEPS.length}
        </DialogTitle>
        <p className="mt-1 text-sm font-medium text-[var(--fg)]">
          {current.title}
        </p>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">{current.body}</p>
        <div className="mt-4 flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <Button size="sm" variant="secondary" asChild>
            <Link href={current.href} onClick={() => close(false)}>
              Open page
            </Link>
          </Button>
          <div className="flex gap-2">
            <Button
              size="sm"
              variant="ghost"
              disabled={step === 0}
              onClick={() => setStep((s) => Math.max(0, s - 1))}
            >
              Back
            </Button>
            {step < STEPS.length - 1 ? (
              <Button size="sm" onClick={() => setStep((s) => s + 1)}>
                Next
              </Button>
            ) : (
              <Button
                size="sm"
                onClick={() => {
                  setChecklistItem("tour", true);
                  close(true);
                }}
              >
                Finish
              </Button>
            )}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function ProductTourTrigger() {
  const [force, setForce] = useState(false);
  return (
    <>
      <Button
        size="sm"
        variant="secondary"
        onClick={() => {
          reopenTour();
          setForce(true);
        }}
      >
        Restart tour
      </Button>
      {force ? (
        <ProductTour forceOpen onClose={() => setForce(false)} />
      ) : null}
    </>
  );
}
