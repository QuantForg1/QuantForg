"use client";

import { memo } from "react";
import Link from "next/link";
import { Cable, Radio } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { str } from "@/lib/desk";

export const ConnectionBar = memo(function ConnectionBar({
  connected,
  server,
  login,
  latencyMs,
  tradingEnabled,
}: {
  connected: boolean;
  server?: unknown;
  login?: unknown;
  latencyMs?: unknown;
  tradingEnabled: boolean;
}) {
  return (
    <div
      className="flex flex-col gap-3 rounded-xl border border-[var(--border)] bg-[var(--surface)]/90 px-4 py-3 sm:flex-row sm:items-center sm:justify-between"
      role="status"
      aria-live="polite"
    >
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone={connected ? "success" : "warning"} className="gap-1.5">
          <span className="qf-status-dot h-1.5 w-1.5 rounded-full bg-current" aria-hidden />
          {connected ? "Connected" : "Disconnected"}
        </Badge>
        <Badge tone={tradingEnabled ? "accent" : "neutral"}>
          {tradingEnabled ? "Gateway ready" : "Live send gated"}
        </Badge>
        <span className="text-xs text-[var(--fg-subtle)]">
          {connected
            ? `${str(server, "MT5")} · login ${str(login, "—")}${
                latencyMs != null ? ` · ${str(latencyMs)} ms` : ""
              }`
            : "Connect a terminal before placing live orders"}
        </span>
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/broker">
            <Cable className="h-3.5 w-3.5" /> Weltrade
          </Link>
        </Button>
        <Button size="sm" variant="ghost" asChild>
          <Link href="/mt5">
            <Radio className="h-3.5 w-3.5" /> MT5
          </Link>
        </Button>
      </div>
    </div>
  );
});
