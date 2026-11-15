"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Phase8LeaderboardDesk } from "@/components/ops/phase8/leaderboard-desk";

export default function ResearchLeaderboardPage() {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <PageHeader
        eyebrow="Research Factory"
        title="Research Leaderboard"
        description="Risk-adjusted ranking with validation classes — never profit-only."
      />
      <PageMotion className="min-h-0 flex-1 overflow-auto p-4">
        <Phase8LeaderboardDesk />
      </PageMotion>
    </div>
  );
}
