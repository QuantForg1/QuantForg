"use client";

import { useQuery } from "@tanstack/react-query";
import { quantitativeResearchControlApi } from "@/lib/api/endpoints";
import { asList, asRecord, str } from "@/lib/desk";
import {
  Phase8Banner,
  Phase8Error,
  Phase8Loading,
  Phase8ModuleNav,
  Phase8Stat,
} from "./shared";

export function Phase8DataDesk() {
  const q = useQuery({
    queryKey: ["p8-data"],
    queryFn: quantitativeResearchControlApi.dataOverview,
    retry: false,
  });
  if (q.isLoading) return <Phase8Loading />;
  if (q.isError) return <Phase8Error message="Research data unavailable." />;
  const data = asRecord(q.data);
  const dq = asRecord(data.data_quality);
  const missing = asList(dq.missing_fields);

  return (
    <div>
      <Phase8ModuleNav current="/research-data" />
      <Phase8Banner tone="neutral">
        Historical data quality workspace. Never fabricates OHLCV. Synthetic data
        must be labeled. Critical missing data blocks experiments.
      </Phase8Banner>
      <div className="mb-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Phase8Stat
          label="Fabricate OHLCV"
          value={data.never_fabricates_ohlcv === false ? "yes" : "no"}
        />
        <Phase8Stat label="IDW" value={str(asRecord(data.idw).status) || "—"} />
        <Phase8Stat label="QCDM" value={str(asRecord(data.qcdm).status) || "—"} />
        <Phase8Stat
          label="Missing sources"
          value={missing.length ? missing.map(String).join(", ") : "none"}
        />
      </div>
    </div>
  );
}
