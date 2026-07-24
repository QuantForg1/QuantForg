"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { QptcmGraduationWorkspace } from "@/components/ops/qptcm-workspaces";

export default function QptcmGraduationPage() {
  return (
    <div>
      <PageHeader
        title="Graduation Workspace"
        description="QPTCM human-gated graduation — never live authorization."
      />
      <PageMotion>
        <QptcmGraduationWorkspace />
      </PageMotion>
    </div>
  );
}
