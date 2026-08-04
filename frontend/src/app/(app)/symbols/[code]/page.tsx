"use client";

import Link from "next/link";
import { use } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { SymbolExperienceWorkspace } from "@/components/ops/symbol-experience-workspace";

export default function SymbolPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = use(params);
  return (
    <div>
      <PageHeader
        title="Symbol"
        description="LIVE chart, spread, signal quality, positions, and history — never fabricated."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/symbol-management">Symbol Management</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/terminal">Terminal</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <SymbolExperienceWorkspace code={code} />
      </PageMotion>
    </div>
  );
}
