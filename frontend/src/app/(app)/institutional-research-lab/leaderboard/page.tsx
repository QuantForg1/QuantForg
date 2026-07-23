"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { IrlLeaderboardWorkspace } from "@/components/ops/irl-workspaces";

export default function IrlLeaderboardPage() {
  return (
    <div>
      <PageHeader
        title="IRL Leaderboard"
        description="Rank research experiments by PF, expectancy, drawdown, consistency, or composite score."
      />
      <PageMotion>
        <IrlLeaderboardWorkspace />
      </PageMotion>
    </div>
  );
}
