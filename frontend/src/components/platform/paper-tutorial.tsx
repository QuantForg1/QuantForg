"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  dismissPaperTutorial,
  isPaperTutorialDismissed,
} from "@/lib/platform/onboarding";

export function PaperTradingTutorial() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    setVisible(!isPaperTutorialDismissed());
  }, []);

  if (!visible) return null;

  return (
    <Card className="mb-4 border-[var(--accent)]/40">
      <CardHeader>
        <CardTitle className="text-base">Paper trading tutorial</CardTitle>
      </CardHeader>
      <CardContent className="space-y-2 text-sm">
        <ol className="list-decimal space-y-1 pl-5 text-[var(--fg-muted)]">
          <li>Confirm symbol and volume in the order form below.</li>
          <li>Click Buy or Sell to submit a paper order (no live broker risk).</li>
          <li>Watch Positions and History update after the fill.</li>
          <li>Use Reset when you want a clean practice book.</li>
        </ol>
        <Button
          size="sm"
          variant="secondary"
          onClick={() => {
            dismissPaperTutorial();
            setVisible(false);
          }}
        >
          Got it
        </Button>
      </CardContent>
    </Card>
  );
}
