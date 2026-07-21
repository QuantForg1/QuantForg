"use client";

import Link from "next/link";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Shield } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { DeskEmpty } from "@/components/desk/primitives";
import { riskApi } from "@/lib/api/endpoints";
import { TRADING_SYMBOL } from "@/lib/trading/gold-only";
import { ApiError } from "@/lib/api/client";
import { useTradingSession } from "@/providers/trading-session-provider";
import { num } from "@/lib/desk";
import { formatCurrency, formatNumber } from "@/lib/utils";

const schema = z.object({
  symbol: z.string().min(1),
  side: z.enum(["buy", "sell"]),
  volume: z.string().min(1),
  stop_loss: z.string().optional(),
  take_profit: z.string().optional(),
});

export default function RiskCenterPage() {
  const session = useTradingSession();
  const equity = num(session.equity);
  const free = num(session.freeMargin);
  const margin = num(session.margin);
  const floating = num(session.profit);
  const used =
    Number.isFinite(equity) && Number.isFinite(free)
      ? Math.max(0, equity - free)
      : NaN;
  const ddPct =
    Number.isFinite(equity) &&
    equity > 0 &&
    Number.isFinite(floating) &&
    floating < 0
      ? (Math.abs(floating) / equity) * 100
      : Number.isFinite(equity) && equity > 0
        ? 0
        : NaN;

  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      symbol: TRADING_SYMBOL,
      side: "buy",
      volume: "0.10",
      stop_loss: "",
      take_profit: "",
    },
  });

  return (
    <div>
      <PageHeader
        title="Risk Center"
        description="Pre-trade checks, live session exposure, and links to deeper risk labs."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/risk-lab">Risk Lab</Link>
            </Button>
            <Button asChild size="sm" variant="secondary">
              <Link href="/book">Book</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />

      <PageMotion className="space-y-4">
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
          <StatCard
            label="Equity"
            value={Number.isFinite(equity) ? formatCurrency(equity) : "—"}
          />
          <StatCard
            label="Free margin"
            value={Number.isFinite(free) ? formatCurrency(free) : "—"}
          />
          <StatCard
            label="Margin used"
            value={
              Number.isFinite(used)
                ? formatCurrency(used)
                : Number.isFinite(margin)
                  ? formatCurrency(margin)
                  : "—"
            }
          />
          <StatCard
            label="Float drawdown"
            value={Number.isFinite(ddPct) ? `${formatNumber(ddPct, 2)}%` : "—"}
            tone={Number.isFinite(ddPct) && ddPct > 2 ? "down" : "neutral"}
          />
        </div>

        <div className="grid gap-4 lg:grid-cols-2">
          <Card className="max-w-xl lg:max-w-none">
            <CardHeader>
              <CardTitle>Risk check</CardTitle>
            </CardHeader>
            <CardContent>
              <form
                className="space-y-3"
                onSubmit={form.handleSubmit(async (values) => {
                  try {
                    const result = await riskApi.check(values);
                    const decision = String(
                      (result as Record<string, unknown>).decision ??
                        (result as Record<string, unknown>).status ??
                        "completed",
                    );
                    toast.success(`Risk check: ${decision}`);
                  } catch (e) {
                    toast.error(
                      e instanceof ApiError ? e.message : "Risk check failed",
                    );
                  }
                })}
              >
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-symbol">Symbol</Label>
                  <Input id="risk-center-symbol" {...form.register("symbol")} />
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-side">Side</Label>
                  <select
                    id="risk-center-side"
                    className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
                    {...form.register("side")}
                  >
                    <option value="buy">Buy</option>
                    <option value="sell">Sell</option>
                  </select>
                </div>
                <div className="space-y-1.5">
                  <Label htmlFor="risk-center-volume">Volume</Label>
                  <Input id="risk-center-volume" {...form.register("volume")} />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div className="space-y-1.5">
                    <Label htmlFor="risk-center-sl">Stop loss</Label>
                    <Input id="risk-center-sl" {...form.register("stop_loss")} />
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="risk-center-tp">Take profit</Label>
                    <Input
                      id="risk-center-tp"
                      {...form.register("take_profit")}
                    />
                  </div>
                </div>
                <Button type="submit">Run risk check</Button>
              </form>
            </CardContent>
          </Card>

          <DeskEmpty
            icon={Shield}
            title="Live rule engine"
            description="PASS / WARN / FAIL rule rows appear on the Terminal ticket after a live risk check. Use Risk Center for pre-trade forms; open Terminal for ticket-bound rules."
            actionLabel="Open Terminal ticket"
            actionHref="/terminal"
          />
        </div>
      </PageMotion>
    </div>
  );
}
