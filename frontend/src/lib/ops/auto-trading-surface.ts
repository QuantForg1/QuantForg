/**
 * Auto Trading page surface — never collapse auth/API waits into "trading down".
 *
 * AUTHENTICATING → LOADING_OPS → READY → DEGRADED → AUTH_REQUIRED /
 * API_UNREACHABLE / UNAVAILABLE
 *
 * UI/telemetry stale is advisory. Hard halt only when Gateway / MT5 / OMS
 * independently report down (or the operator cannot authenticate a submit).
 */

import { classifyCommunicationFault } from "../api/communication-fault";
import type { AuthPhase } from "../auth/bootstrap";

export type AutoTradingSurface =
  | "AUTHENTICATING"
  | "LOADING_OPS"
  | "READY"
  | "DEGRADED"
  | "UNAVAILABLE"
  | "AUTH_REQUIRED"
  | "API_UNREACHABLE";

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
  | "validation"
  | "error";

/** After this wait, slow ops with healthy infra is DEGRADED — not a full-page auth wait. */
export const OPS_SLOW_MS = 8_000;

export function classifyOpsFailure(error: {
  status?: number;
  code?: string;
} | null | undefined): OpsQueryKind {
  if (!error) return "error";
  const fault = classifyCommunicationFault(error);
  if (fault === "API_TIMEOUT") return "timeout";
  if (fault === "AUTH_REQUIRED" || fault === "AUTH_REFRESH") return "unauthorized";
  if (fault === "FORBIDDEN") return "forbidden";
  if (fault === "CONTRACT_VALIDATION_ERROR") return "validation";
  if (fault === "API_UNREACHABLE") return "error";
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
  if (input.opsQuery === "validation") return "API_DEGRADED";
  if (input.opsQuery === "error" && input.infra === "TRADING_HEALTHY") return "API_DEGRADED";
  if (input.opsQuery === "error") return "API_UNREACHABLE";
  return "API_DEGRADED";
}

export type AutoTradingSurfaceResult = {
  surface: AutoTradingSurface;
  apiPhase: ApiPhase;
  tradingInfra: TradingInfraState;
  /** Disable Execute Now in this browser (auth/API/hard infra). */
  blockNewEntries: boolean;
  /** True only when Gateway / MT5 / OMS independently report down. */
  haltsAutonomousTrading: boolean;
  reportGatewayDisconnected: boolean;
  reportMt5Disconnected: boolean;
  reportBrokerDisconnected: boolean;
};

const noDisconnects = {
  reportGatewayDisconnected: false,
  reportMt5Disconnected: false,
  reportBrokerDisconnected: false,
} as const;

function operatorCannotSubmit(authPhase: AuthPhase, opsQuery: OpsQueryKind): boolean {
  return (
    authPhase === "AUTH_LOADING" ||
    authPhase === "AUTH_REQUIRED" ||
    opsQuery === "unauthorized" ||
    opsQuery === "forbidden"
  );
}

export function resolveAutoTradingSurface(input: {
  authPhase: AuthPhase;
  opsQuery: OpsQueryKind;
  hasOpsData: boolean;
  tradingInfra: TradingInfraState;
  opsWaitMs?: number;
  opsFresh?: boolean;
}): AutoTradingSurfaceResult {
  const apiPhase = resolveApiPhase({
    opsQuery: input.opsQuery,
    infra: input.tradingInfra,
  });
  const tradingInfra = input.tradingInfra;
  const opsFresh = input.opsFresh ?? (input.opsQuery === "success" && input.hasOpsData);
  const hardHalt = tradingInfra === "TRADING_DEGRADED";
  const authBlocksSubmit = operatorCannotSubmit(input.authPhase, input.opsQuery);

  const pack = (
    surface: AutoTradingSurface,
    extra?: { blockNewEntries?: boolean; apiPhase?: ApiPhase },
  ): AutoTradingSurfaceResult => ({
    surface,
    apiPhase: extra?.apiPhase ?? apiPhase,
    tradingInfra,
    blockNewEntries: extra?.blockNewEntries ?? (authBlocksSubmit || hardHalt),
    haltsAutonomousTrading: hardHalt,
    ...noDisconnects,
  });

  if (input.authPhase === "AUTH_LOADING") {
    return pack("AUTHENTICATING", { blockNewEntries: true });
  }

  if (input.authPhase === "AUTH_REQUIRED" || input.opsQuery === "unauthorized") {
    return pack("AUTH_REQUIRED", { blockNewEntries: true });
  }

  if (input.opsQuery === "forbidden") {
    return pack("UNAVAILABLE", { blockNewEntries: true });
  }

  if (input.opsQuery === "success" && input.hasOpsData) {
    const degraded = hardHalt || !opsFresh;
    return pack(degraded ? "DEGRADED" : "READY");
  }

  if (input.opsQuery === "timeout" || input.opsQuery === "error" || input.opsQuery === "validation") {
    if (input.opsQuery === "error" && tradingInfra === "UNKNOWN" && !input.hasOpsData) {
      return pack("API_UNREACHABLE", {
        apiPhase: "API_UNREACHABLE",
        blockNewEntries: true,
      });
    }
    return pack("DEGRADED");
  }

  // In-flight ops: keep last-known-good on screen. Stay LOADING_OPS until the
  // request settles — do not flip to DEGRADED on browser RTT (~8–12s).
  if (input.opsQuery === "idle" || input.opsQuery === "loading") {
    if (input.hasOpsData) {
      const freshEnough = opsFresh && !hardHalt;
      return pack(freshEnough ? "READY" : "DEGRADED");
    }
    return pack("LOADING_OPS");
  }

  return pack("UNAVAILABLE", { blockNewEntries: true });
}

export function autoTradingSurfaceCopy(result: AutoTradingSurfaceResult): {
  title: string;
  detail: string;
} {
  if (result.surface === "AUTHENTICATING") {
    return { title: "Authenticating", detail: "Restoring session before loading Auto Trading." };
  }
  if (result.surface === "LOADING_OPS") {
    return {
      title: "Loading ops telemetry",
      detail:
        result.tradingInfra === "TRADING_HEALTHY"
          ? "Trading infrastructure is healthy. Loading authenticated Auto Trading telemetry."
          : "Loading authenticated Auto Trading telemetry.",
    };
  }
  if (result.surface === "AUTH_REQUIRED") {
    return {
      title: "Sign in required",
      detail: "Your session expired. Sign in again. Trading infrastructure is not reported down.",
    };
  }
  if (result.surface === "API_UNREACHABLE") {
    return {
      title: "API unreachable",
      detail:
        "The API did not respond. This is not a Gateway, MT5, or broker disconnect unless those planes independently report down.",
    };
  }
  if (result.surface === "DEGRADED") {
    if (result.tradingInfra === "TRADING_HEALTHY") {
      return {
        title: "Ops telemetry delayed",
        detail:
          "Trading infrastructure is healthy. Auto Trading ops telemetry is stale or timed out — this does not halt new entries.",
      };
    }
    if (result.haltsAutonomousTrading) {
      return {
        title: "Auto Trading blocked",
        detail:
          "Gateway, MT5, or OMS reported down. New entries stay hard-blocked until those planes recover.",
      };
    }
    return {
      title: "Auto Trading degraded",
      detail:
        "Ops telemetry is delayed. This is not a Gateway, MT5, or broker disconnect unless those planes independently report down.",
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
