"use client";

import { ExecutionDiagnosticsPanel } from "@/components/execution/execution-diagnostics";

/** Full MT5 execution audit trail — Validation → Risk → Gateway → order_check → order_send. */
export default function ExecutionDiagnosticsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-4 p-4 md:p-6">
      <header>
        <h1 className="text-xl font-semibold tracking-tight text-[var(--fg)]">
          Execution Diagnostics
        </h1>
        <p className="mt-1 text-sm text-[var(--fg-muted)]">
          Institutional audit of every live order attempt. No mock data.
        </p>
      </header>
      <ExecutionDiagnosticsPanel />
    </div>
  );
}
