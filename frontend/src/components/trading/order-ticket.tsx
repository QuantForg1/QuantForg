"use client";

import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { mt5Api, executionApi } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";

const schema = z.object({
  symbol: z.string().min(1),
  side: z.enum(["buy", "sell"]),
  order_type: z.enum(["market", "limit"]),
  volume: z.string().min(1),
  price: z.string().optional(),
  stop_loss: z.string().optional(),
  take_profit: z.string().optional(),
  request_id: z.string().min(1),
});

type FormValues = z.infer<typeof schema>;

export function OrderTicket() {
  const form = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      symbol: "EURUSD",
      side: "buy",
      order_type: "market",
      volume: "0.01",
      price: "",
      stop_loss: "",
      take_profit: "",
      request_id: `req_${Date.now()}`,
    },
  });

  return (
    <Card>
      <CardHeader>
        <CardTitle>Order ticket</CardTitle>
      </CardHeader>
      <CardContent>
        <form
          className="grid gap-3 sm:grid-cols-2"
          onSubmit={form.handleSubmit(async (values) => {
            try {
              const payload = {
                ...values,
                price: values.price || null,
                stop_loss: values.stop_loss || null,
                take_profit: values.take_profit || null,
                slippage: 10,
                magic: 0,
                comment: "quantforg-ui",
              };
              const validation = await mt5Api.validateOrder(payload);
              toast.message("Validation", {
                description: String(validation.valid ?? validation.message ?? "checked"),
              });
              await executionApi.check(payload);
              toast.success("Execution safety check completed (live send remains gated).");
            } catch (e) {
              toast.error(e instanceof ApiError ? e.message : "Order check failed");
            }
          })}
        >
          {(
            [
              ["symbol", "Symbol"],
              ["volume", "Volume"],
              ["price", "Price"],
              ["stop_loss", "Stop loss"],
              ["take_profit", "Take profit"],
              ["request_id", "Request ID"],
            ] as const
          ).map(([key, label]) => (
            <div key={key} className="space-y-1.5">
              <Label htmlFor={key}>{label}</Label>
              <Input id={key} {...form.register(key)} />
            </div>
          ))}
          <div className="space-y-1.5">
            <Label htmlFor="side">Side</Label>
            <select
              id="side"
              className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
              {...form.register("side")}
            >
              <option value="buy">Buy</option>
              <option value="sell">Sell</option>
            </select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor="order_type">Type</Label>
            <select
              id="order_type"
              className="flex h-10 w-full rounded-md border border-[var(--border)] bg-[var(--surface)] px-3 text-sm"
              {...form.register("order_type")}
            >
              <option value="market">Market</option>
              <option value="limit">Limit</option>
            </select>
          </div>
          <div className="sm:col-span-2">
            <Button type="submit" className="w-full" disabled={form.formState.isSubmitting}>
              Validate & risk-check
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
