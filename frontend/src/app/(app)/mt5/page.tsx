"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useForm } from "react-hook-form";
import { z } from "zod";
import { zodResolver } from "@hookform/resolvers/zod";
import { toast } from "sonner";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { mt5Api } from "@/lib/api/endpoints";
import { ApiError } from "@/lib/api/client";
import { FeatureGate } from "@/components/platform/feature-gate";

const schema = z.object({
  login: z.coerce.number().int().positive(),
  password: z.string().min(1),
  server: z.string().min(1),
  path: z.string().optional(),
});

export default function Mt5Page() {
  const qc = useQueryClient();
  const status = useQuery({ queryKey: ["mt5-status"], queryFn: mt5Api.status, retry: false });
  const form = useForm<z.infer<typeof schema>>({
    resolver: zodResolver(schema),
    defaultValues: { login: 0, password: "", server: "", path: "" },
  });

  const connect = useMutation({
    mutationFn: mt5Api.connect,
    onSuccess: async () => {
      toast.success("MT5 connected");
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("broker_connect", "success", "MT5 terminal connected", { server: form.getValues("server") });
      await qc.invalidateQueries({ queryKey: ["mt5-status"] });
    },
    onError: async (e) => {
      const { recordAudit } = await import("@/lib/observability/audit");
      const { captureError } = await import("@/lib/observability/error-monitor");
      recordAudit("broker_connect", "failure", "MT5 connect failed");
      captureError("mt5", e, { path: "/mt5/connect" });
      toast.error(e instanceof ApiError ? e.message : "Connect failed");
    },
  });

  const disconnect = useMutation({
    mutationFn: mt5Api.disconnect,
    onSuccess: async () => {
      toast.success("MT5 disconnected");
      const { recordAudit } = await import("@/lib/observability/audit");
      recordAudit("broker_disconnect", "success", "MT5 terminal disconnected");
      await qc.invalidateQueries({ queryKey: ["mt5-status"] });
    },
    onError: async (e) => {
      const { recordAudit } = await import("@/lib/observability/audit");
      const { captureError } = await import("@/lib/observability/error-monitor");
      recordAudit("broker_disconnect", "failure", "MT5 disconnect failed");
      captureError("mt5", e, { path: "/mt5/disconnect" });
      toast.error(e instanceof ApiError ? e.message : "Disconnect failed");
    },
  });

  return (
    <FeatureGate flag="mt5" label="MT5">
    <div>
      <PageHeader
        title="MT5 Accounts"
        description="Connect, monitor, and disconnect MetaTrader 5 terminals."
        actions={
          <Badge tone={status.data?.connected ? "success" : "warning"}>
            {status.isLoading
              ? "Checking…"
              : status.data?.connected
                ? "Connected"
                : "Disconnected"}
          </Badge>
        }
      />
      {status.isLoading ? (
        <DeskSkeleton rows={4} />
      ) : status.isError ? (
        <DeskError
          message="Unable to load MT5 status."
          onRetry={() => status.refetch()}
        />
      ) : (
      <div className="grid gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Connect terminal</CardTitle>
          </CardHeader>
          <CardContent>
            <form
              className="space-y-3"
              onSubmit={form.handleSubmit((values) => connect.mutate(values))}
            >
              <div className="space-y-1.5">
                <Label htmlFor="mt5-login">Login</Label>
                <Input id="mt5-login" type="number" {...form.register("login")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mt5-password">Password</Label>
                <Input id="mt5-password" type="password" autoComplete="current-password" {...form.register("password")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mt5-server">Server</Label>
                <Input id="mt5-server" {...form.register("server")} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="mt5-path">Terminal path (optional)</Label>
                <Input id="mt5-path" {...form.register("path")} />
              </div>
              <div className="flex gap-2">
                <Button type="submit" disabled={connect.isPending}>
                  Connect
                </Button>
                <Button
                  type="button"
                  variant="secondary"
                  onClick={() => disconnect.mutate()}
                  disabled={disconnect.isPending}
                >
                  Disconnect
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Session</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm text-[var(--fg-muted)]">
            <p>Server: {String(status.data?.server || "—")}</p>
            <p>Login status: {String(status.data?.login_status || "—")}</p>
            <p>Latency: {String(status.data?.latency_ms ?? "—")} ms</p>
            <p className="text-xs text-[var(--fg-muted)]">
              Shared process terminals are session-bound on the API — only the live tenant can read market state.
            </p>
          </CardContent>
        </Card>
      </div>
      )}
    </div>
    </FeatureGate>
  );
}
