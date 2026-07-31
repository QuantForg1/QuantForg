"use client";

import { asRecord, str } from "@/lib/desk";
import { Badge } from "@/components/ui/badge";
import { NocPanel, NocRow, fmt } from "@/components/ops/noc/noc-primitives";

const WAITING = "Waiting for first eligible production execution.";

export function ProductionAcceptancePanel({
  data,
}: {
  data: Record<string, unknown>;
}) {
  const verified = Boolean(data.verified) || str(data.status).toUpperCase() === "VERIFIED";
  const latest = asRecord(data.latest_execution);
  const hasExecution = Boolean(latest.validation_id || data.latest_broker_ticket);

  return (
    <NocPanel
      title="Production Acceptance"
      action={
        <Badge tone={verified ? "success" : "warning"}>
          {verified ? "VERIFIED" : "NOT VERIFIED"}
        </Badge>
      }
    >
      {!hasExecution ? (
        <p className="text-[12px] text-[var(--fg-muted)]">{WAITING}</p>
      ) : (
        <div className="space-y-0.5">
          <NocRow
            label="Status"
            value={verified ? "VERIFIED" : "NOT VERIFIED"}
            tone={verified ? "ok" : "warn"}
          />
          <NocRow label="Latest broker ticket" value={fmt(data.latest_broker_ticket)} />
          <NocRow
            label="Latest execution"
            value={
              latest.validation_id
                ? `${str(latest.decision, "—")} · ${str(latest.symbol, "—")} · ${str(
                    latest.validation_id,
                    "—",
                  ).slice(0, 20)}`
                : "—"
            }
          />
          <NocRow
            label="Latest latency"
            value={
              data.latest_latency_ms == null ? "—" : `${data.latest_latency_ms} ms`
            }
          />
          <NocRow
            label="Latest certificate"
            value={
              data.latest_certificate
                ? str(data.latest_certificate)
                : verified
                  ? "Production_Acceptance_Certificate.md"
                  : "—"
            }
          />
          {data.message ? (
            <p className="mt-2 text-[11px] text-[var(--fg-subtle)]">{str(data.message)}</p>
          ) : null}
          <p className="mt-2 text-[10px] text-[var(--fg-subtle)]">
            Observe-only · real broker tickets only · never fabricated
          </p>
        </div>
      )}
    </NocPanel>
  );
}
