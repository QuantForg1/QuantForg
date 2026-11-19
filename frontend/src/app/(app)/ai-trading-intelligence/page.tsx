"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase4AtiDesk } from "@/components/intelligence/phase4-ati-desk";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function AiTradingIntelligencePage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Intelligence"
        title="AI Trading Intelligence"
        description="Market regime, signal quality, optimizer evidence, and supervisor controls — advisory only."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link href="/intelligence">Market desk</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/robot-control-center">Robot &amp; Risk</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/research">Research</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/decision-evidence">Decision evidence</Link>
            </Button>
          </div>
        }
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase4AtiDesk />
      </PageMotion>
    </div>
  );
}
