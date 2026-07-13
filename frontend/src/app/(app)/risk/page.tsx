"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { riskApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

const schema = z.object({
  symbol: z.string().min(1),
  side: z.enum(["buy", "sell"]),
  volume: z.string().min(1),
  stop_loss: z.string().optional(),
  take_profit: z.string().optional(),
});

export default function RiskPage() {
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: {
      symbol: "EURUSD",
      side: "buy",
      volume: "0.10",
      stop_loss: "",
      take_profit: "",
    },
  });

  return (
    <div>
      <PageHeader
        title="Risk Management"
        description="Pre-trade risk checks and exposure controls."
      />
      <Card className="max-w-xl">
        <CardHeader>
          <CardTitle>Risk check</CardTitle>
        </CardHeader>
        <CardContent>
          <form
            className="space-y-3"
            onSubmit={form.handleSubmit(async (values) => {
              try {
                const result = await riskApi.check(values);
                toast.success("Risk check completed");
                void result;
              } catch (e) {
                toast.error(e instanceof ApiError ? e.message : "Risk check failed");
              }
            })}
          >
            <div className="space-y-1.5">
              <Label>Symbol</Label>
              <Input {...form.register("symbol")} />
            </div>
            <div className="space-y-1.5">
              <Label>Side</Label>
              <select
                className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
                {...form.register("side")}
              >
                <option value="buy">Buy</option>
                <option value="sell">Sell</option>
              </select>
            </div>
            <div className="space-y-1.5">
              <Label>Volume</Label>
              <Input {...form.register("volume")} />
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1.5">
                <Label>Stop loss</Label>
                <Input {...form.register("stop_loss")} />
              </div>
              <div className="space-y-1.5">
                <Label>Take profit</Label>
                <Input {...form.register("take_profit")} />
              </div>
            </div>
            <Button type="submit">Run risk check</Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
