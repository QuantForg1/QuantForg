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
    title: "Terminal",
    body: "Trade here. Chart, ticket, and blotter — keyboard first. ⌘1 opens Terminal anytime.",
    href: "/terminal",
  },
  {
    title: "Book",
    body: "Portfolio, risk, and P&L from live session data. Empty when disconnected — never fabricated.",
    href: "/book",
  },
  {
    title: "Research & Counsel",
    body: "Build and validate strategies in Research. Counsel is decision intelligence — advisory only, never auto-trades.",
    href: "/research",
  },
  {
    title: "Broker",
    body: "Attach your MT5 session. The browser never talks to the terminal directly.",
    href: "/broker",
  },
  {
    title: "Journal",
    body: "Session memory and post-trade notes. Use Inbox for alerts.",
    href: "/journal",
  },
] as const;

type ProductTourProps = {
  forceOpen?: boolean;
  onClose?: () => void;
};

/**
 * Optional orientation. Does not auto-open after first login —
 * only when forceOpen (Settings) or if never dismissed and explicitly reopened.
 */
export function ProductTour({ forceOpen = false, onClose }: ProductTourProps) {
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    if (forceOpen) {
      setOpen(true);
      setStep(0);
      return;
    }
    // Do not interrupt the trading day after first login.
    if (!isTourDismissed()) dismissTour();
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
          {current.title}
          <span className="ml-2 text-xs font-normal text-[var(--fg-muted)]">
            {step + 1}/{STEPS.length}
          </span>
        </DialogTitle>
        <p className="mt-2 text-sm text-[var(--fg-muted)]">{current.body}</p>
        <div className="mt-6 flex flex-wrap items-center gap-2">
          <Button asChild variant="secondary" size="sm">
            <Link href={current.href} onClick={() => close(false)}>
              Open
            </Link>
          </Button>
          {step < STEPS.length - 1 ? (
            <Button
              size="sm"
              onClick={() => {
                setStep((s) => s + 1);
              }}
            >
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
              Done
            </Button>
          )}
          <Button variant="ghost" size="sm" onClick={() => close(true)}>
            Skip
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export { reopenTour };

export function ProductTourTrigger() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <Button
        variant="secondary"
        size="sm"
        onClick={() => {
          reopenTour();
          setOpen(true);
        }}
      >
        Orient me
      </Button>
      {open ? <ProductTour forceOpen onClose={() => setOpen(false)} /> : null}
    </>
  );
}
