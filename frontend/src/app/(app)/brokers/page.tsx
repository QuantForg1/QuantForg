"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import { Cable, PlugZap } from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskEmpty, DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { brokersApi, mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

const FEATURED = [
  { key: "mt5", name: "MT5", match: /mt5|meta.?trader/i, href: "/mt5" },
  { key: "ib", name: "Interactive Brokers", match: /interactive|ibkr|ib\b/i, href: "/brokers" },
  { key: "bybit", name: "Bybit", match: /bybit/i, href: "/brokers" },
  { key: "binance", name: "Binance", match: /binance/i, href: "/brokers" },
  { key: "ctrader", name: "cTrader", match: /ctrader/i, href: "/brokers" },
];

export default function BrokersPage() {
  const brokers = useQuery({ queryKey: ["brokers"], queryFn: brokersApi.list, retry: false });
  const accounts = useQuery({
    queryKey: ["broker-accounts"],
    queryFn: brokersApi.accounts,
    retry: false,
  });
  const connections = useQuery({
    queryKey: ["broker-connections"],
    queryFn: brokersApi.connections,
    retry: false,
  });
  const mt5 = useQuery({ queryKey: ["mt5-status"], queryFn: mt5Api.status, retry: false });

  const brokerList = asList(brokers.data).map(asRecord);
  const accountList = asList(accounts.data).map(asRecord);
  const connectionList = asList(connections.data).map(asRecord);

  const cards = FEATURED.map((f) => {
    const matched = brokerList.find((b) => f.match.test(`${str(b.name)} ${str(b.slug)} ${str(b.platform_code)}`));
    const account = accountList.find((a) => str(a.broker_id) === str(matched?.id));
    const connection = connectionList.find((c) => str(c.broker_account_id) === str(account?.id));
    const isMt5 = f.key === "mt5";
    const connected = isMt5
      ? Boolean(mt5.data?.connected)
      : ["connected", "active", "online"].includes(str(connection?.status ?? account?.connection_status, "").toLowerCase());
    const lastSync = isMt5
      ? str(mt5.data?.server, "—")
      : str(connection?.last_connected_at ?? connection?.updated_at ?? account?.updated_at, "—");
    return {
      ...f,
      status: connected ? "Connected" : str(matched?.status ?? "Available", "Available"),
      connected,
      lastSync: lastSync.slice(0, 19),
      latency: isMt5 && mt5.data?.connected ? "< 50 ms" : "—",
      description: str(matched?.description, `${f.name} brokerage connectivity`),
    };
  });

  const loading = brokers.isLoading && accounts.isLoading;

  return (
    <div>
      <PageHeader
        title="Broker Accounts"
        description="Manage venue connectivity, sync health, and session latency."
        actions={
          <Button asChild size="sm">
            <Link href="/mt5">
              <PlugZap className="h-3.5 w-3.5" /> Connect MT5
            </Link>
          </Button>
        }
      />

      {loading ? (
        <DeskSkeleton rows={4} />
      ) : brokers.isError && accounts.isError ? (
        <DeskError message="Unable to load brokers." onRetry={() => brokers.refetch()} />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {cards.map((c) => (
              <Card key={c.key} className="transition hover:border-[var(--accent)]/30">
                <CardHeader className="flex-row items-start justify-between gap-2">
                  <div>
                    <CardTitle>{c.name}</CardTitle>
                    <p className="mt-1 text-xs text-[var(--fg-subtle)]">{c.description}</p>
                  </div>
                  <Badge tone={c.connected ? "success" : "warning"}>{c.status}</Badge>
                </CardHeader>
                <CardContent className="space-y-3">
                  <div className="grid grid-cols-2 gap-2 text-xs text-[var(--fg-muted)]">
                    <div>
                      <p className="text-[var(--fg-subtle)]">Last sync</p>
                      <p className="tabular text-[var(--fg)]">{c.lastSync}</p>
                    </div>
                    <div>
                      <p className="text-[var(--fg-subtle)]">Latency</p>
                      <p className="tabular text-[var(--fg)]">{c.latency}</p>
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button size="sm" asChild>
                      <Link href={c.href}>Connect</Link>
                    </Button>
                    <Button size="sm" variant="secondary" asChild>
                      <Link href={c.key === "mt5" ? "/mt5" : "/brokers"}>Disconnect</Link>
                    </Button>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Registered brokers</CardTitle>
            </CardHeader>
            <CardContent>
              {brokerList.length === 0 ? (
                <DeskEmpty
                  icon={Cable}
                  title="No broker accounts connected."
                  description="Connect a venue to begin syncing accounts and sessions."
                  actionLabel="Connect Broker"
                  onAction={() => {
                    window.location.href = "/mt5";
                  }}
                />
              ) : (
                <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                  {brokerList.map((b) => (
                    <div
                      key={str(b.id)}
                      className="rounded-lg border border-[var(--border)] bg-[var(--surface-2)] px-3 py-3"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="text-sm font-medium">{str(b.name)}</p>
                        <Badge tone="neutral">{str(b.status)}</Badge>
                      </div>
                      <p className="mt-1 text-xs text-[var(--fg-subtle)]">
                        {str(b.platform_code)} · {str(b.broker_type)}
                      </p>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
