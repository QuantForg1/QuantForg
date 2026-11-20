import { StrategyDetail } from "@/components/trading/strategy-detail";

export default async function MarketplaceStrategyPage({
  params,
}: {
  params: Promise<{ key: string }>;
}) {
  const { key } = await params;
  return <StrategyDetail strategyKey={decodeURIComponent(key)} />;
}
