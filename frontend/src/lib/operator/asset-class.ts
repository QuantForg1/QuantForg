/** Classify symbols into institutional asset classes for heatmap / analytics. */

export type AssetClass =
  | "forex"
  | "crypto"
  | "metals"
  | "indices"
  | "energy"
  | "other";

export function classifyAsset(symbol: string): AssetClass {
  const u = symbol.trim().toUpperCase();
  if (!u) return "other";
  if (/XAU|XAG|GOLD|SILVER/.test(u)) return "metals";
  if (/BTC|ETH|SOL|XRP|DOGE|ADA|CRYPTO|USDT|USDC/.test(u)) return "crypto";
  if (/XTI|XBR|OIL|BRENT|WTI|NATGAS|XNG|CL/.test(u)) return "energy";
  if (/US30|US500|NAS|SPX|DAX|UK100|JP225|GER40|NDX|DJ/.test(u)) return "indices";
  if (/^[A-Z]{6}$/.test(u) || /USD|EUR|GBP|JPY|AUD|CAD|CHF|NZD/.test(u)) {
    return "forex";
  }
  return "other";
}

export const ASSET_LABELS: Record<AssetClass, string> = {
  forex: "Forex",
  crypto: "Crypto",
  metals: "Metals",
  indices: "Indices",
  energy: "Energy",
  other: "Other",
};
