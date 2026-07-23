"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { AqsPatternsWorkspace } from "@/components/ops/aqs-workspaces";

export default function AqsPatternsPage() {
  return (
    <div>
      <PageHeader title="AQS Pattern Explorer" description="Pattern discovery and weakness detection." />
      <PageMotion>
        <AqsPatternsWorkspace />
      </PageMotion>
    </div>
  );
}
