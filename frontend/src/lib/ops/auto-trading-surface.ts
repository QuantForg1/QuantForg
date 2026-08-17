/**
 * Auto Trading page surface — never collapse auth/API waits into "trading down".
 *
 * LOADING → AUTHENTICATING → READY → DEGRADED → UNAVAILABLE / AUTH_REQUIRED
 */

import type { AuthPhase } from "../auth/bootstrap";

export type AutoTradingSurface =
  | "LOADING"
  | "AUTHENTICATING"
  | "READY"
  | "DEGRADED"
  | "UNAVAILABLE"
  | "AUTH_REQUIRED";

export type ApiPhase =
  | "API_LOADING"
  | "API_READY"
  | "API_DEGRADED"
  | "API_UNREACHABLE";

export type TradingInfraState = "TRADING_HEALTHY" | "TRADING_DEGRADED" | "UNKNOWN";

export type OpsQueryKind =
  | "idle"
  | "loading"
  | "success"
  | "timeout"
  | "unauthorized"
  | "forbidden"
  | "error";

export function classifyOpsFailure(error: {
  status?: number;
  code?: string;
} | null | undefined): OpsQueryKind {
  if (!error) return "error";
  if (error.code === "timeout" || error.status === 408) return "timeout";
  if (
    error.status === 401 ||
    error.code === "unauthorized" ||
    error.code === "missing_token" ||
    error.code === "authentication_failed"
  ) {
    return "unauthorized";
  }
  if (error.status === 403 || error.code === "insufficient_role") return "forbidden";
  if (error.code === "network_error" || error.status === 0) return "error";
  return "error";
}

export function resolveTradingInfraState(input: {
  gatewayOk: boolean | null | undefined;
  mt5Ok: boolean | null | undefined;
  omsOk: boolean | null | undefined;
}): TradingInfraState {
  const planes = [input.gatewayOk, input.mt5Ok, input.omsOk];
  if (planes.every((p) => p === true)) return "TRADING_HEALTHY";
  if (planes.some((p) => p === false)) return "TRADING_DEGRADED";
  return "UNKNOWN";
}

export function resolveApiPhase(input: {
  opsQuery: OpsQueryKind;
  infra: TradingInfraState;
}): ApiPhase {
  if (input.opsQuery === "idle" || input.opsQuery === "loading") return "API_LOADING";
  if (input.opsQuery === "success") return "API_READY";
  if (input.opsQuery === "timeout") return "API_DEGRADED";
  if (input.opsQuery === "error" && input.infra === "TRADING_HEALTHY") return "API_DEGRADED";
  if (input.opsQuery === "error") return "API_UNREACHABLE";
  return "API_DEGRADED";
}

export type AutoTradingSurfaceResult = {
  surface: AutoTradingSurface;
  apiPhase: ApiPhase;
  tradingInfra: TradingInfraState;
  blockNewEntries: boolean;
  /** Timeouts / auth must never set these. */
  reportGatewayDisconnected: boolean;
  reportMt5Disconnected: boolean;
  reportBrokerDisconnected: boolean;
};

const noDisconnects = {
  reportGatewayDisconnected: false,
  reportMt5Disconnected: false,
  reportBrokerDisconnected: false,
} as const;

export function resolveAutoTradingSurface(input: {
  authPhase: AuthPhase;
  opsQuery: OpsQueryKind;
  hasOpsData: boolean;
  tradingInfra: TradingInfraState;
}): AutoTradingSurfaceResult {
  const apiPhase = resolveApiPhase({
    opsQuery: input.opsQuery,
    infra: input.tradingInfra,
  });
  const tradingInfra = input.tradingInfra;

  if (input.authPhase === "AUTH_LOADING") {
    return {
      surface: "AUTHENTICATING",
      apiPhase,
      tradingInfra,
      blockNewEntries: true,
      ...noDisconnects,
    };
  }

  if (input.authPhase === "AUTH_REQUIRED" || input.opsQuery === "unauthorized") {
    return {
      surface: "AUTH_REQUIRED",
      apiPhase,
      tradingInfra,
      blockNewEntries: true,
      ...noDisconnects,
    };
  }

  if (input.opsQuery === "idle" || input.opsQuery === "loading") {
    return {
      surface: "LOADING",
      apiPhase,
      tradingInfra,
      blockNewEntries: true,
      ...noDisconnects,
    };
  }

  if (input.opsQuery === "forbidden") {
    return {
      surface: "UNAVAILABLE",
      apiPhase,
      tradingInfra,
      blockNewEntries: true,
      ...noDisconnects,
    };
  }

  if (input.opsQuery === "success" && input.hasOpsData) {
    const degraded = tradingInfra === "TRADING_DEGRADED";
    return {
      surface: degraded ? "DEGRADED" : "READY",
      apiPhase,
      tradingInfra,
      blockNewEntries: degraded,
      ...noDisconnects,
    };
  }

  // Timeout / error: infra from trading-components stays independent.
  // A frontend timeout is never Gateway/MT5/Broker disconnected.
  if (input.opsQuery === "timeout" || input.opsQuery === "error") {
    return {
      surface: "DEGRADED",
      apiPhase,
      tradingInfra,
      blockNewEntries: true,
      ...noDisconnects,
    };
  }

  return {
    surface: "UNAVAILABLE",
    apiPhase,
    tradingInfra,
    blockNewEntries: true,
    ...noDisconnects,
  };
}

export function autoTradingSurfaceCopy(result: AutoTradingSurfaceResult): {
  title: string;
  detail: string;
} {
  if (result.surface === "AUTHENTICATING") {
    return { title: "Authenticating", detail: "Restoring session before loading Auto Trading." };
  }
  if (result.surface === "LOADING") {
    return { title: "Loading Auto Trading", detail: "Waiting for authenticated ops data." };
  }
  if (result.surface === "AUTH_REQUIRED") {
    return {
      title: "Sign in required",
      detail: "Your session expired. Sign in again. Trading infrastructure is not reported down.",
    };
  }
  if (result.surface === "DEGRADED") {
    if (result.tradingInfra === "TRADING_HEALTHY") {
      return {
        title: "Ops telemetry delayed",
        detail:
          "Trading infrastructure is healthy. Auto Trading ops did not respond in time — new entries stay blocked until the API recovers.",
      };
    }
    return {
      title: "Auto Trading degraded",
      detail:
        "The API did not respond in time. This is not a Gateway, MT5, or broker disconnect unless those planes independently report down.",
    };
  }
  if (result.surface === "UNAVAILABLE") {
    return {
      title: "Auto Trading unavailable",
      detail: "OWNER/ADMIN access is required for ITE ops controls.",
    };
  }
  return { title: "Auto Trading", detail: "" };
}
