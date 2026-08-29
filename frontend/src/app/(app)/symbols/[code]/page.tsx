"use client";

import { InstrumentDetail } from "@/components/trading/instrument-detail";
import { use } from "react";

export default function SymbolPage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = use(params);
  return <InstrumentDetail code={decodeURIComponent(code)} />;
}
