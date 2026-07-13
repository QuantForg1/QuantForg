"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  CHECKLIST_ITEMS,
  checklistProgress,
  dismissFirstRun,
  getChecklist,
  isFirstRunDismissed,
  setChecklistItem,
  type ChecklistState,
} from "@/lib/platform/onboarding";

export function FirstRunChecklist() {
  const [visible, setVisible] = useState(false);
  const [state, setState] = useState<ChecklistState | null>(null);

  useEffect(() => {
    if (isFirstRunDismissed()) return;
    setState(getChecklist());
    setVisible(true);
  }, []);

  if (!visible || !state) return null;

  const progress = checklistProgress(state);

  return (
    <div
      className="border-b border-[var(--border)] bg-[var(--surface-2)] px-4 py-3"
      role="region"
      aria-label="Closed beta first-run checklist"
    >
      <div className="mx-auto flex max-w-6xl flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div className="space-y-1">
          <p className="text-sm font-medium text-[var(--fg)]">
            Welcome to QuantForg Closed Beta
          </p>
          <p className="text-xs text-[var(--fg-muted)]">
            First-run checklist · {progress.done}/{progress.total} complete
          </p>
          <ul className="mt-1 flex flex-wrap gap-2">
            {CHECKLIST_ITEMS.map((item) => (
              <li key={item.id}>
                <Link
                  href={item.href}
                  className="inline-flex items-center gap-1 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-xs hover:bg-[var(--surface-2)]"
                  onClick={() => setState(setChecklistItem(item.id, state[item.id]))}
                >
                  <span aria-hidden>{state[item.id] ? "✓" : "○"}</span>
                  {item.title}
                </Link>
              </li>
            ))}
          </ul>
        </div>
        <div className="flex shrink-0 gap-2">
          <Button size="sm" variant="secondary" asChild>
            <Link href="/get-started">Open guide</Link>
          </Button>
          <Button
            size="sm"
            variant="ghost"
            onClick={() => {
              dismissFirstRun();
              setVisible(false);
            }}
          >
            Dismiss
          </Button>
        </div>
      </div>
    </div>
  );
}
