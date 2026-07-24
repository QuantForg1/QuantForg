"use client";

import { Suspense } from "react";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { DeskSkeleton } from "@/components/desk/primitives";
import { QemCorrelationWorkspace } from "@/components/ops/qem-workspaces";

export default function QuantForgEventMeshCorrelationPage() {
  return (
    <div>
      <PageHeader
        title="Correlation Viewer"
        description="QEM correlation groups — loosely coupled event relationships."
      />
      <PageMotion>
        <Suspense fallback={<DeskSkeleton rows={6} />}>
          <QemCorrelationWorkspace />
        </Suspense>
      </PageMotion>
    </div>
  );
}
