"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { InstitutionalAlphaWorkspace } from "@/components/ops/institutional-alpha-workspace";

export default function InstitutionalAlphaPage() {
  return (
    <div>
      <PageHeader
        title="Institutional Alpha Engine"
        description="Multi-symbol opportunity ranking, correlation protection, adaptive risk, and portfolio analytics — extends Auto Trading without bypassing Risk, Safety, or OMS."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/portfolio-analytics">Portfolio Analytics</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <InstitutionalAlphaWorkspace />
      </PageMotion>
    </div>
  );
}
