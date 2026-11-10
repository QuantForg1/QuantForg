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

function errorCode(error: unknown): string {
  if (!(error instanceof ApiError)) return "";
  return String(error.code || "").toUpperCase();
}

/** True when the API indicates the broker trading session is closed. */
export function isMarketClosedApiError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  const code = errorCode(error);
  if (
    code === "MARKET_FEED_UNAVAILABLE" ||
    code === "GATEWAY_UNAVAILABLE" ||
    code === "MT5_UNAVAILABLE" ||
    code === "CLOUDFLARE_ORIGIN_UNREACHABLE"
  ) {
    return false;
  }
  const msg = errorBlob(error);
  // Never treat a bare HTTP 503 as market-closed — feed/gateway outages are 503 too.
  return (
    msg.includes("market closed") ||
    msg.includes("market_closed") ||
    msg.includes("trade is disabled") ||
    msg.includes("session closed") ||
    msg.includes("markets are closed")
  );
}

/** True when the platform market feed / origin is unreachable. */
export function isMarketFeedUnavailableError(error: unknown): boolean {
  if (!(error instanceof ApiError)) return false;
  const code = errorCode(error);
  const msg = errorBlob(error);
  return (
    code === "MARKET_FEED_UNAVAILABLE" ||
    code === "GATEWAY_UNAVAILABLE" ||
    code === "MT5_UNAVAILABLE" ||
    code === "CLOUDFLARE_ORIGIN_UNREACHABLE" ||
    msg.includes("market data feed unavailable") ||
    msg.includes("gateway is unavailable") ||
    msg.includes("cloudflare_origin_unreachable") ||
    msg.includes("error code: 1033") ||
    (error.status === 503 && !isMarketClosedApiError(error))
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
    if (isMarketFeedUnavailableError(error)) {
      return "Platform market feed offline. Symbol catalogue temporarily unavailable.";
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
    if (isMarketFeedUnavailableError(error)) {
      return `Platform market feed offline for ${symbol}. Retry shortly — personal broker login is not required.`;
    }
    if (isMarketClosedApiError(error)) {
      return `Market closed for ${symbol}. Historical candles remain available when the feed has them.`;
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
  return `Unable to load candles for ${symbol}.`;
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
  if (isMarketFeedUnavailableError(error)) {
    return { marketOpen: null, quoteDetail: "Feed Offline" };
  }
  return { marketOpen: null, quoteDetail: "No Tick" };
}

export type PublicFeedStatus = "live" | "closed" | "delayed" | "unavailable";

export function publicFeedBadge(status: string | null | undefined): {
  label: string;
  tone: "ok" | "warn" | "danger" | "muted";
} {
  switch ((status || "").toLowerCase()) {
    case "live":
      return { label: "LIVE", tone: "ok" };
    case "closed":
      return { label: "MARKET CLOSED", tone: "warn" };
    case "delayed":
      return { label: "DELAYED", tone: "warn" };
    case "loading":
      return { label: "LOADING", tone: "muted" };
    case "unavailable":
      return { label: "UNAVAILABLE", tone: "danger" };
    default:
      return { label: "OFFLINE", tone: "muted" };
  }
}
