"use client";

import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { StrategyLeaderboardWorkspace } from "@/components/operator/strategy-leaderboard-workspace";

export default function Page() {
  return (
    <div>
      <PageHeader
        title="Strategy Leaderboard"
        description="LIVE ranking for SMC, Trend, Momentum, Breakout, Mean Reversion."
      />
      <PageMotion>
        <StrategyLeaderboardWorkspace />
      </PageMotion>
    </div>
  );
}
