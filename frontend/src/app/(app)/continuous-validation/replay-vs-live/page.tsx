"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { CvfReplayVsLiveWorkspace } from "@/components/ops/cvf-workspaces";

export default function CvfReplayVsLivePage() {
  return (
    <div>
      <PageHeader
        title="Replay vs Live"
        description="Compare research/replay baselines with live portfolio observations."
      />
      <PageMotion>
        <CvfReplayVsLiveWorkspace />
      </PageMotion>
    </div>
  );
}
