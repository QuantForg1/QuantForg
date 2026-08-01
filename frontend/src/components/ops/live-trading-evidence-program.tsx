"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { Activity } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DeskEmpty,
  DeskError,
  DeskSkeleton,
  DeskTable,
} from "@/components/desk/primitives";
import { NocPanel, NocRow } from "@/components/ops/noc/noc-primitives";
import { liveTradingEvidenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { useAuth } from "@/providers/auth-provider";
import {
  canAccessIteOps,
  iteOpsAccessDeniedMessage,
} from "@/lib/auth/ite-ops-access";

type Section =
  | "overview"
  | "trades"
  | "investigate"
  | "rejections"
  | "dashboard"
  | "readiness";

function fmt(v: unknown, fallback = "—"): string {
  if (v === null || v === undefined || v === "") return fallback;
  if (typeof v === "boolean") return v ? "yes" : "no";
  if (typeof v === "number") return Number.isFinite(v) ? String(v) : fallback;
  return String(v);
}

/**
 * Live Trading Readiness & Evidence — RC4 ops desk.
 * Observe-only. Never fabricates trade fields. Never forces trades.
 */
export function LiveTradingEvidenceProgram() {
  const { user } = useAuth();
  const allowed = canAccessIteOps(user);
  const [section, setSection] = useState<Section>("overview");
  const [tradeId, setTradeId] = useState("");

  const programQ = useQuery({
    queryKey: ["live-trading-evidence-program"],
    queryFn: () => liveTradingEvidenceApi.program(),
    enabled: allowed,
    refetchInterval: 20_000,
    retry: false,
  });

  const investigateQ = useQuery({
    queryKey: ["live-trading-evidence-investigate", tradeId],
    queryFn: () => liveTradingEvidenceApi.investigate(tradeId),
    enabled: allowed && section === "investigate" && tradeId.trim().length > 0,
    retry: false,
  });

  const data = asRecord(programQ.data);
  const flags = asRecord(data.flags);
  const tradesPack = asRecord(data.live_trade_evidence);
  const tradeRows = asList(tradesPack.trades);
  const rejectsPack = asRecord(data.rejected_opportunities);
  const rejectRows = asList(rejectsPack.rejections);
  const dash = asRecord(data.evidence_dashboard);
  const readiness = asRecord(data.production_readiness);
  const archive = asRecord(data.execution_archive);
  const inv = asRecord(investigateQ.data);

  const sections = useMemo(
    () =>
      [
        ["overview", "Overview"],
        ["trades", "Trade Evidence"],
        ["investigate", "Investigate"],
        ["rejections", "Rejections"],
        ["dashboard", "Dashboard"],
        ["readiness", "Readiness"],
      ] as const,
    [],
  );

  if (!allowed) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          undefined,
          "Live Trading Evidence",
        )}
      />
    );
  }
  if (programQ.isLoading && !programQ.data) return <DeskSkeleton rows={12} />;
  if (programQ.error && !programQ.data) {
    return (
      <DeskError
        message={iteOpsAccessDeniedMessage(
          user,
          programQ.error,
          "Live Trading Evidence",
        )}
      />
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="accent">Evidence v1</Badge>
        <Badge tone="success">
          trading · {fmt(flags.modifies_trading, "false")}
        </Badge>
        <Badge tone="success">
          fabricate · {fmt(flags.fabricates_evidence, "false")}
        </Badge>
        <Button asChild size="sm" variant="outline">
          <Link href="/admin/noc">
            <Activity className="mr-1 size-3.5" />
            NOC
          </Link>
        </Button>
      </div>

      <div className="flex flex-wrap gap-1.5">
        {sections.map(([id, label]) => (
          <Button
            key={id}
            size="sm"
            variant={section === id ? "secondary" : "ghost"}
            onClick={() => setSection(id)}
          >
            {label}
          </Button>
        ))}
      </div>

      {section === "overview" ? (
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          <NocPanel id="lte-exec" title="Executed Evidence">
            <NocRow label="Trades archived" value={fmt(tradesPack.count, "0")} />
            <NocRow
              label="Archive count"
              value={fmt(archive.count ?? tradesPack.archive_count, "0")}
            />
            <NocRow
              label="Rejected"
              value={fmt(rejectsPack.count, "0")}
            />
          </NocPanel>
          <NocPanel id="lte-dash" title="Evidence Dashboard">
            <NocRow
              label="AI approval rate"
              value={fmt(dash.ai_approval_rate)}
            />
            <NocRow
              label="Avg latency"
              value={fmt(dash.average_latency)}
            />
            <NocRow
              label="Avg slippage"
              value={fmt(dash.average_slippage)}
            />
          </NocPanel>
          <NocPanel id="lte-ready" title="Production Readiness">
            <NocRow label="Score" value={fmt(readiness.score)} />
            <NocRow label="Status" value={fmt(readiness.status)} />
            <NocRow
              label="Measured components"
              value={fmt(readiness.measured_components, "0")}
            />
          </NocPanel>
        </div>
      ) : null}

      {section === "trades" ? (
        tradeRows.length === 0 ? (
          <DeskEmpty
            icon={Activity}
            title="Waiting for first eligible production execution"
            description="Evidence archives only when a real execution package with ticket/acceptance exists."
          />
        ) : (
          <DeskTable
            columns={[
              "Trade ID",
              "Symbol",
              "Direction",
              "Entry",
              "Exit",
              "PnL",
              "Latency",
            ]}
            rows={tradeRows.map((row) => {
              const r = asRecord(row);
              return [
                str(r.trade_id, "—"),
                str(r.symbol, "—"),
                str(r.direction, "—"),
                fmt(r.entry),
                fmt(r.exit),
                fmt(r.pnl),
                fmt(r.latency),
              ];
            })}
          />
        )
      ) : null}

      {section === "investigate" ? (
        <div className="space-y-3">
          <div className="flex flex-wrap items-end gap-2">
            <label className="text-[12px] text-[var(--muted-foreground)]">
              Trade ID / ticket / validation ID
              <input
                className="mt-1 block w-72 rounded border border-[var(--border)] bg-[var(--surface)] px-2 py-1 text-[13px]"
                value={tradeId}
                onChange={(e) => setTradeId(e.target.value)}
                placeholder="e.g. validation_id or mt5 ticket"
              />
            </label>
            {tradeRows[0] ? (
              <Button
                size="sm"
                variant="outline"
                onClick={() =>
                  setTradeId(str(asRecord(tradeRows[0]).trade_id, ""))
                }
              >
                Use latest
              </Button>
            ) : null}
          </div>
          {!tradeId.trim() ? (
            <DeskEmpty
              icon={Activity}
              title="Enter a Trade ID"
              description="Investigation loads pipeline, AI/risk explain, OMS, broker, management, and replay refs."
            />
          ) : investigateQ.isLoading ? (
            <DeskSkeleton rows={8} />
          ) : inv.ok === false ? (
            <DeskEmpty
              icon={Activity}
              title="Not found"
              description={str(inv.note, "No archived evidence for this id.")}
            />
          ) : (
            <div className="grid gap-3 md:grid-cols-2">
              <NocPanel id="inv-ai" title="AI explanation">
                <NocRow
                  label="Decision"
                  value={fmt(asRecord(inv.ai_explanation).decision)}
                />
                <NocRow
                  label="Quality"
                  value={fmt(asRecord(inv.ai_explanation).quality)}
                />
                <NocRow
                  label="Confidence"
                  value={fmt(asRecord(inv.ai_explanation).confidence)}
                />
              </NocPanel>
              <NocPanel id="inv-risk" title="Risk explanation">
                <NocRow
                  label="Risk score"
                  value={fmt(asRecord(inv.risk_explanation).risk_score)}
                />
                <NocRow
                  label="RR"
                  value={fmt(asRecord(inv.risk_explanation).rr)}
                />
                <NocRow
                  label="Size"
                  value={fmt(asRecord(inv.risk_explanation).position_size)}
                />
              </NocPanel>
              <NocPanel id="inv-pipe" title="Pipeline / timeline">
                <NocRow
                  label="Stages"
                  value={fmt(asList(inv.pipeline).length, "0")}
                />
                <NocRow
                  label="Management events"
                  value={fmt(asList(inv.management_events).length, "0")}
                />
                <NocRow
                  label="Replay"
                  value={fmt(asRecord(inv.replay).href, "/replay-evidence-lab")}
                />
              </NocPanel>
              <NocPanel id="inv-oms" title="OMS / Broker">
                <NocRow
                  label="OMS latency"
                  value={fmt(asRecord(inv.oms_events).latency_ms)}
                />
                <NocRow
                  label="Broker slippage"
                  value={fmt(asRecord(inv.broker_response).slippage)}
                />
                <NocRow
                  label="Broker status"
                  value={fmt(
                    asRecord(inv.broker_response).execution_status,
                  )}
                />
              </NocPanel>
            </div>
          )}
        </div>
      ) : null}

      {section === "rejections" ? (
        rejectRows.length === 0 ? (
          <DeskEmpty
            icon={Activity}
            title="No rejection evidence yet"
            description="Rejections appear from cycle evidence / PVM no-trade records — reasons never fabricated."
          />
        ) : (
          <DeskTable
            columns={[
              "Gate",
              "Reason",
              "Quality",
              "Confidence",
              "Session",
              "Timestamp",
            ]}
            rows={rejectRows.map((row) => {
              const r = asRecord(row);
              return [
                str(r.blocking_gate, "—"),
                str(r.reason, "—"),
                fmt(r.quality),
                fmt(r.confidence),
                fmt(r.session),
                fmt(r.timestamp),
              ];
            })}
          />
        )
      ) : null}

      {section === "dashboard" ? (
        <div className="grid gap-3 md:grid-cols-2">
          <NocPanel id="dash" title="Institutional Evidence Dashboard">
            <NocRow
              label="Executed trades"
              value={fmt(dash.executed_trades, "0")}
            />
            <NocRow
              label="Rejected trades"
              value={fmt(dash.rejected_trades, "0")}
            />
            <NocRow
              label="Execution quality"
              value={fmt(dash.execution_quality)}
            />
            <NocRow
              label="AI approval rate"
              value={fmt(dash.ai_approval_rate)}
            />
            <NocRow
              label="Execution rate"
              value={fmt(dash.execution_rate)}
            />
            <NocRow
              label="Average slippage"
              value={fmt(dash.average_slippage)}
            />
            <NocRow
              label="Average latency"
              value={fmt(dash.average_latency)}
            />
          </NocPanel>
          <NocPanel id="dash-sym" title="Symbols">
            <NocRow
              label="Best"
              value={
                asList(dash.best_symbols)
                  .map((r) => str(asRecord(r).symbol))
                  .join(", ") || "—"
              }
            />
            <NocRow
              label="Worst"
              value={
                asList(dash.worst_symbols)
                  .map((r) => str(asRecord(r).symbol))
                  .join(", ") || "—"
              }
            />
          </NocPanel>
        </div>
      ) : null}

      {section === "readiness" ? (
        <NocPanel id="ready" title="Production Readiness Score">
          <NocRow label="Score" value={fmt(readiness.score)} />
          <NocRow label="Status" value={fmt(readiness.status)} />
          <NocRow
            label="Measured components"
            value={fmt(readiness.measured_components, "0")}
          />
          <NocRow label="Note" value={str(readiness.note, "—")} />
          <DeskTable
            columns={["Component", "Score"]}
            rows={asList(readiness.components).map((row) => {
              const r = asRecord(row);
              return [str(r.id), fmt(r.score)];
            })}
          />
        </NocPanel>
      ) : null}
    </div>
  );
}
