/**
 * Independent market / gateway / catalogue status helpers.
 * Never conflate market-closed or missing ticks with gateway downtime.
 */

import { ApiError } from "@/lib/api/client";

function errorBlob(error: unknown): string {
  if (!(error instanceof ApiError)) {
    return error instanceof Error ? error.message.toLowerCase() : String(error).toLowerCase();
  }
  return `${error.message} ${JSON.stringify(error.details ?? {})}`.toLowerCase();
}

/** True when the API indicates the broker trading session is closed. */
export function isMarketClosedApiError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  const msg = errorBlob(error);
  return (
    error.status === 503 ||
    msg.includes("market closed") ||
    msg.includes("market_closed") ||
    msg.includes("trade is disabled") ||
    msg.includes("session closed") ||
    msg.includes("markets are closed") ||
    msg.includes("symbol_select")
  );
}

/**
 * Symbol catalogue load failure — gateway vs catalogue vs market-closed stay distinct.
 */
export function catalogueLoadErrorMessage(
  error: unknown,
  gatewayOnline: boolean | null,
): string {
  if (error instanceof ApiError) {
    if (error.status === 401 || error.code === "unauthorized") {
      return "Session expired. Please sign in again.";
    }
    if (isMarketClosedApiError(error)) {
      return "Market closed. Symbol quotes may be unavailable until the trading session opens.";
    }
    if (error.code === "timeout") {
      return "Catalogue degraded — backend delayed. Tap Retry.";
    }
    if (error.status === 404) {
      return gatewayOnline === true
        ? "Symbol catalogue awaiting broker session bind. Retry shortly."
        : "Broker session not attached. Open Broker to reconnect.";
    }
    if (error.code === "network_error") {
      return gatewayOnline === true
        ? "Symbol catalogue temporarily unavailable from the broker feed."
        : "API unreachable. Symbol catalogue temporarily unavailable.";
    }
  }
  return gatewayOnline === true
    ? "Symbol catalogue unavailable from the broker feed."
    : "Catalogue degraded. Open Broker if reconnect is needed.";
}

/** Candle load failure — market-closed must not read as gateway down. */
export function candleLoadErrorMessage(
  error: unknown,
  symbol: string,
  gatewayOnline: boolean | null,
): string {
  if (error instanceof ApiError) {
    if (isMarketClosedApiError(error)) {
      return `Market closed. Candles unavailable for ${symbol} outside the trading session.`;
    }
    if (error.status === 401 || error.code === "unauthorized") {
      return "Session expired. Please sign in again.";
    }
    if (error.code === "timeout") {
      return "Backend response delayed while loading candles. Tap Retry.";
    }
    if (error.code === "network_error") {
      return gatewayOnline === true
        ? `Candle data temporarily unavailable for ${symbol}.`
        : "API unreachable. Candle data temporarily unavailable.";
    }
  }
  return "Unable to load candles from MT5.";
}

/** Tick load failure classification for independent Quote vs Market Open lines. */
export function tickLoadStatus(error: unknown | null | undefined): {
  marketOpen: boolean | null;
  quoteDetail: string;
} {
  if (!error) {
    return { marketOpen: null, quoteDetail: "No Tick" };
  }
  if (isMarketClosedApiError(error)) {
    return { marketOpen: false, quoteDetail: "No Tick" };
  }
  return { marketOpen: null, quoteDetail: "No Tick" };
}
