"use client";

import Link from "next/link";
import { useQuery } from "@tanstack/react-query";
import { institutionalIntelligenceApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import { Button } from "@/components/ui/button";
import {
  Phase6Banner,
  Phase6Empty,
  Phase6Error,
  Phase6Loading,
  Phase6ModuleNav,
  Phase6Stat,
} from "./shared";

export function Phase6PortfolioDesk() {
  const q = useQuery({
    queryKey: ["p6-portfolio"],
    queryFn: institutionalIntelligenceApi.portfolio,
    retry: false,
    staleTime: 15_000,
  });

  if (q.isLoading) return <Phase6Loading />;
  if (q.isError) {
    return <Phase6Error message="Portfolio optimization overview unavailable." />;
  }

  const data = asRecord(q.data);
  const rules = asRecord(data.rules);
  const household = asRecord(data.household);
  const qpm = asRecord(data.qpm);
  const recommendations = asList(qpm.recommendations);

  return (
    <div>
      <Phase6ModuleNav current="/portfolio-optimization" />
      <Phase6Banner tone="warn">
        Recommendations only — never auto-rebalance LIVE accounts. Capital,
        equity and margin are never invented.
      </Phase6Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase6Stat
          label="Auto rebalance"
          value={rules.never_auto_rebalance === false ? "on" : "off"}
        />
        <Phase6Stat
          label="Equity present"
          value={household.equity_present === true ? "yes" : "no"}
        />
        <Phase6Stat
          label="Balance present"
          value={household.balance_present === true ? "yes" : "no"}
        />
        <Phase6Stat label="Recommendations" value={recommendations.length} />
      </div>
      {recommendations.length === 0 ? (
        <Phase6Empty message="No QPM recommendations available — honest empty state." />
      ) : (
        <ul className="mb-4 divide-y divide-border/50 rounded-md border border-border/60">
          {recommendations.slice(0, 30).map((item, i) => {
            const row = asRecord(item);
            return (
              <li key={i} className="px-3 py-2 text-sm">
                {str(row.title) || str(row.id) || `Recommendation ${i + 1}`}
              </li>
            );
          })}
        </ul>
      )}
      <div className="flex flex-wrap gap-2">
        <Button size="sm" variant="secondary" asChild>
          <Link href="/quantforg-portfolio-manager">QPM desk</Link>
        </Button>
        <Button size="sm" variant="secondary" asChild>
          <Link href="/book">Book / household</Link>
        </Button>
      </div>
    </div>
  );
}
