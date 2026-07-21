"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AlphaEngineWorkspace } from "@/components/ops/alpha-engine-workspace";

export default function AlphaEnginePage() {
  return (
    <div>
      <PageHeader
        title="Alpha Engine V1"
        description="Institutional market-quality scoring for XAUUSD before execution. Advisory only — never invents market data, never places orders, never promises profitability. Integrates with Decision Center without changing Risk or Safety."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/decision-intelligence">Decision Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/market-intelligence">Market Intel</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <AlphaEngineWorkspace />
      </PageMotion>
    </div>
  );
}
