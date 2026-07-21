"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { PageMotion } from "@/components/desk/motion";
import { TradeReplayPanel } from "@/components/journal/trade-replay";

export default function TradeReplayPage() {
  return (
    <div>
      <PageHeader
        title="Trade Replay"
        description="Immutable execution audit stages for closed trades. Select a deal in Orders History to load a request timeline."
        actions={
          <Button asChild size="sm" variant="secondary">
            <Link href="/journal/orders">Orders History</Link>
          </Button>
        }
      />
      <PageMotion>
        <Card>
          <CardContent className="p-4">
            <TradeReplayPanel />
          </CardContent>
        </Card>
      </PageMotion>
    </div>
  );
}
