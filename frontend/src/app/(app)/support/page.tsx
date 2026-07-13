"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { motion } from "framer-motion";
import {
  BookOpen,
  HeartPulse,
  LifeBuoy,
  Mail,
  Ticket,
} from "lucide-react";
import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { DeskError, DeskSkeleton } from "@/components/desk/primitives";
import { platformApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";

export default function SupportPage() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: platformApi.health,
    retry: false,
  });
  const version = useQuery({
    queryKey: ["version"],
    queryFn: platformApi.version,
  });

  const deps = asList(health.data?.dependencies).map(asRecord);
  const status = str(health.data?.status, "unknown");
  const healthy = status === "healthy" || status === "alive";

  return (
    <div>
      <PageHeader
        title="Support"
        description="Status, documentation, and escalation paths for the trading desk."
        actions={
          <Button size="sm" asChild>
            <a href="mailto:support@quantforg.com?subject=QuantForg%20Support%20Ticket">
              <Ticket className="h-3.5 w-3.5" /> Support Ticket
            </a>
          </Button>
        }
      />

      {health.isLoading ? (
        <DeskSkeleton rows={3} />
      ) : health.isError ? (
        <DeskError
          message="Unable to load platform health."
          onRetry={() => health.refetch()}
        />
      ) : (
        <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="space-y-4">
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardHeader className="flex-row items-center justify-between">
                <CardTitle className="flex items-center gap-2 text-base">
                  <HeartPulse className="h-4 w-4 text-[var(--accent)]" /> Status
                </CardTitle>
                <Badge tone={healthy ? "success" : "warning"}>{status}</Badge>
              </CardHeader>
              <CardContent className="text-sm text-[var(--fg-muted)]">
                API {str(version.data?.version, "…")} · {str(health.data?.environment, "env")}
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <BookOpen className="h-4 w-4 text-[var(--accent)]" /> Documentation
                </CardTitle>
              </CardHeader>
              <CardContent className="text-sm text-[var(--fg-muted)]">
                Use in-product desks for portfolio, risk, paper, and MT5. Backend contracts remain
                under <code>/api/v1</code>.
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <Mail className="h-4 w-4 text-[var(--accent)]" /> Contact
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-[var(--fg-muted)]">
                <p>Escalate via organization owners and include API request IDs.</p>
                <Button size="sm" variant="secondary" asChild>
                  <a href="mailto:support@quantforg.com">Email support</a>
                </Button>
              </CardContent>
            </Card>
            <Card>
              <CardHeader>
                <CardTitle className="flex items-center gap-2 text-base">
                  <LifeBuoy className="h-4 w-4 text-[var(--accent)]" /> System Health
                </CardTitle>
              </CardHeader>
              <CardContent>
                <Button size="sm" variant="secondary" asChild>
                  <Link href="/ops">Open operations</Link>
                </Button>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Recent Incidents</CardTitle>
            </CardHeader>
            <CardContent>
              {deps.length === 0 ? (
                <p className="text-sm text-[var(--fg-muted)]">
                  No dependency incidents reported in the latest health probe.
                </p>
              ) : (
                <ul className="space-y-2">
                  {deps.map((d) => (
                    <li
                      key={str(d.name)}
                      className="flex items-center justify-between rounded-lg border border-[var(--border)] px-3 py-2"
                    >
                      <span className="text-sm">{str(d.name)}</span>
                      <Badge
                        tone={
                          str(d.status) === "healthy"
                            ? "success"
                            : str(d.status) === "disabled"
                              ? "neutral"
                              : "warning"
                        }
                      >
                        {str(d.status)}
                      </Badge>
                    </li>
                  ))}
                </ul>
              )}
              <p className="mt-4 text-xs text-[var(--fg-subtle)]">
                Live trading remains gated by <code>EXECUTION_ENABLED</code>.
              </p>
            </CardContent>
          </Card>
        </motion.div>
      )}
    </div>
  );
}
