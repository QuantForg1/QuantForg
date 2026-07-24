"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { Rc1Workspace } from "@/components/ops/rc1-workspace";

export default function Rc1Page() {
  return (
    <div>
      <PageHeader
        title="Release Candidate"
        description="RC1 — Production readiness checklist, smoke tests (no real trades), live statistics, go-live score, and capital scaling advice. Evidence before scale-up."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/production-reliability">Hardening</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/research-platform">Research</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/performance-lab">Performance Lab</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <Rc1Workspace />
      </PageMotion>
    </div>
  );
}
