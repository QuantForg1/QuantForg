"use client";

import { useQuery } from "@tanstack/react-query";
import { weltradeApi } from "@/lib/api/endpoints";
import { asRecord, str } from "@/lib/desk";
import {
  gatewayDiagnosticDetail,
  gatewayStatusLabel,
} from "@/lib/gateway-diagnostics";
import { cn } from "@/lib/utils";

type Props = {
  className?: string;
  compact?: boolean;
};

/** Compact Railway ↔ Cloudflare ↔ MT5 Gateway status strip for ops surfaces. */
export function WeltradeGatewayStatus({ className, compact = false }: Props) {
  const healthQ = useQuery({
    queryKey: ["weltrade-health"],
    queryFn: weltradeApi.health,
    refetchInterval: 10_000,
    retry: 1,
  });

  const health = asRecord(healthQ.data);
  const online = Boolean(health.gateway_online || health.gateway_reachable);
  const mt5 = Boolean(health.mt5_connected || health.mt5_attached);
  const label = gatewayStatusLabel(health);
  const detail = gatewayDiagnosticDetail(health);
  const gatewayUrl = str(health.gateway_url);
  const latency = health.latency ?? health.latency_ms;
  const redirects = health.redirects_followed;
  const cf = asRecord(health.cloudflare);

  return (
    <div
      className={cn(
        "rounded-xl border border-[var(--border)] bg-[var(--surface)]/90 px-3 py-3",
        className,
      )}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-[0.14em] text-[var(--fg-subtle)]">
          MT5 Gateway
        </p>
        <span
          className={cn(
            "text-xs font-medium",
            online ? "text-[var(--success)]" : "text-[var(--fg)]",
          )}
        >
          {healthQ.isLoading ? "Checking…" : label}
        </span>
      </div>
      {!compact ? (
        <div className="mt-2 grid gap-1 text-[11px] text-[var(--fg-muted)] sm:grid-cols-2">
          <span>MT5: {mt5 ? "Connected" : "Not connected"}</span>
          <span>
            Latency:{" "}
            {latency != null && latency !== "" ? `${String(latency)} ms` : "—"}
          </span>
          <span>
            Cloudflare: {cf.detected ? "yes" : "no"}
            {redirects != null && redirects !== ""
              ? ` · redirects ${String(redirects)}`
              : ""}
          </span>
          <span className="truncate">
            Login: {str(health.login_status, "—")}
          </span>
        </div>
      ) : null}
      {!online && detail && detail !== "ok" ? (
        <p className="mt-2 break-words font-mono text-[11px] text-[var(--fg)]">
          {detail.slice(0, 240)}
        </p>
      ) : null}
      {gatewayUrl ? (
        <p className="mt-1 truncate text-[10px] text-[var(--fg-subtle)]">
          {gatewayUrl}
        </p>
      ) : null}
    </div>
  );
}
