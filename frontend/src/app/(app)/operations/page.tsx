"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase5OperationsDesk } from "@/components/ops/phase5/operations-desk";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function OperationsPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Control Center"
        title="Operations"
        description="Platform status, robot controls, and links across Phase 5 operational modules."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="secondary" asChild>
              <Link href="/quantforg-operations-center">AOC (read-only)</Link>
            </Button>
            <Button size="sm" variant="secondary" asChild>
              <Link href="/mission-control">Mission Control</Link>
            </Button>
          </div>
        }
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase5OperationsDesk />
      </PageMotion>
    </div>
  );
}
