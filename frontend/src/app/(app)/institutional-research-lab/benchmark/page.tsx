"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlBenchmarkWorkspace } from "@/components/ops/irl-workspaces";

export default function IrlBenchmarkPage() {
  return (
    <div>
      <PageHeader
        title="IRL Benchmark"
        description="Compare candidate research results against the production baseline reference. Never auto-promotes."
      />
      <PageMotion>
        <IrlBenchmarkWorkspace />
      </PageMotion>
    </div>
  );
}
