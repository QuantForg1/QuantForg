import { mt5Api } from "@/lib/api/endpoints";
import { asList, asRecord, num, str } from "@/lib/desk";

export type Mt5BarPayload = {
  open_time: string;
  open: string;
  high: string;
  low: string;
  close: string;
  volume: string;
  close_time?: string;
};

/**
 * Load OHLC bars from the MT5 gateway via backend.
 * Never invents bars — returns [] when gateway has no data.
 */
export async function loadBarsFromMt5Gateway(
  symbol: string,
  timeframe: string,
  count: number,
): Promise<Mt5BarPayload[]> {
  const raw = await mt5Api.candles(symbol, timeframe, count);
  const rows = asList(raw).map(asRecord);
  const bars: Mt5BarPayload[] = [];

  for (const r of rows) {
    const open = num(r.open);
    const high = num(r.high);
    const low = num(r.low);
    const close = num(r.close);
    if (![open, high, low, close].every(Number.isFinite)) continue;
    const openTime = str(r.open_time);
    if (!openTime) continue;
    const vol = num(r.tick_volume ?? r.volume, 0);
    bars.push({
      open_time: openTime,
      open: open.toFixed(5),
      high: high.toFixed(5),
      low: low.toFixed(5),
      close: close.toFixed(5),
      volume: String(Number.isFinite(vol) ? Math.max(0, Math.round(vol)) : 0),
      close_time: str(r.close_time) || undefined,
    });
  }

  return bars;
}
