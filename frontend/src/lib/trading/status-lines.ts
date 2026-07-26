/**
 * Independent trading status lines — never invent contradictory states.
 * Trading Enabled requires an explicit backend enablement confirmation
 * and a connected broker path.
 */

export type StatusTone = "ok" | "warn" | "off" | "unknown";

export type TradingStatusLine = {
  id: "gateway" | "broker" | "market" | "trading" | "feed";
  label: string;
  value: string;
  tone: StatusTone;
};

export type TradingStatusInput = {
  /** Explicit gateway reachability from health; null = unknown. */
  gatewayOnline: boolean | null;
  /** Explicit broker/MT5 session; null = unknown. */
  brokerConnected: boolean | null;
  /** Market session / quotes available; null = unknown. */
  marketOpen: boolean | null;
  /**
   * Server-confirmed execution enablement.
   * null = unknown (do not infer Enabled from connectivity alone).
   */
  executionEnabled: boolean | null;
  /** Data feed: live | delayed | offline | null unknown. */
  feed: "live" | "delayed" | "offline" | null;
};

function line(
  id: TradingStatusLine["id"],
  label: string,
  value: string,
  tone: StatusTone,
): TradingStatusLine {
  return { id, label, value, tone };
}

/**
 * Derive five independent status lines.
 * Rule: never report Trading Enabled when broker is disconnected,
 * unless executionEnabled === true is explicitly confirmed by backend
 * AND broker is connected.
 */
export function deriveTradingStatusLines(
  input: TradingStatusInput,
): TradingStatusLine[] {
  const gateway =
    input.gatewayOnline == null
      ? line("gateway", "Gateway", "Unknown", "unknown")
      : input.gatewayOnline
        ? line("gateway", "Gateway", "Connected", "ok")
        : line("gateway", "Gateway", "Disconnected", "off");

  const broker =
    input.brokerConnected == null
      ? line("broker", "Broker", "Unknown", "unknown")
      : input.brokerConnected
        ? line("broker", "Broker", "Connected", "ok")
        : line("broker", "Broker", "Disconnected", "off");

  const market =
    input.marketOpen == null
      ? line("market", "Market", "Unknown", "unknown")
      : input.marketOpen
        ? line("market", "Market", "Open", "ok")
        : line("market", "Market", "Closed", "warn");

  let trading: TradingStatusLine;
  if (input.executionEnabled == null) {
    trading = line("trading", "Trading", "Unknown", "unknown");
  } else if (input.executionEnabled === true) {
    // Backend says enabled — still refuse to show Enabled if broker is known disconnected.
    if (input.brokerConnected === false) {
      trading = line("trading", "Trading", "Disabled", "off");
    } else if (input.brokerConnected == null) {
      trading = line("trading", "Trading", "Unknown", "unknown");
    } else {
      trading = line("trading", "Trading", "Enabled", "ok");
    }
  } else {
    trading = line("trading", "Trading", "Disabled", "off");
  }

  const feed =
    input.feed == null
      ? line("feed", "Data Feed", "Unknown", "unknown")
      : input.feed === "live"
        ? line("feed", "Data Feed", "Live", "ok")
        : input.feed === "delayed"
          ? line("feed", "Data Feed", "Delayed", "warn")
          : line("feed", "Data Feed", "Offline", "off");

  return [gateway, broker, market, trading, feed];
}
