"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { PageMotion } from "@/components/desk/motion";
import { SessionStrip } from "@/components/broker/session-strip";
import { PortfolioIntelligenceLab } from "@/components/book/portfolio-intelligence-lab";
import { BookEmpty } from "@/components/book/empty-state";
import { useTradingSession } from "@/providers/trading-session-provider";

export default function AllocationPage() {
  const session = useTradingSession();

  return (
    <div>
      <PageHeader
        title="Allocation"
        description="VaR, correlation, and capital allocation from live portfolio intelligence."
        actions={
          <Button asChild size="sm" variant="secondary">
            <Link href="/portfolio">Portfolio OS</Link>
          </Button>
        }
      />
      <SessionStrip className="mb-4" />
      <PageMotion>
        {!session.connected ? (
          <BookEmpty
            title="No allocation data"
            description="Portfolio intelligence loads after MT5 sync. QuantForg never fabricates risk figures."
            action={
              <Button size="sm" variant="secondary" asChild>
                <Link href="/broker">Open Broker</Link>
              </Button>
            }
          />
        ) : (
          <PortfolioIntelligenceLab />
        )}
      </PageMotion>
    </div>
  );
}
