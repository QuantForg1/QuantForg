/**
 * Control-plane communication faults.
 * Never collapse these into a trading NO_TRADE decision.
 */

export const COMMUNICATION_FAULTS = [
  "API_UNREACHABLE",
  "API_TIMEOUT",
  "AUTH_REQUIRED",
  "AUTH_REFRESH",
  "CONTRACT_VALIDATION_ERROR",
  "FORBIDDEN",
  "SERVER_ERROR",
  "OK",
] as const;

export type CommunicationFault = (typeof COMMUNICATION_FAULTS)[number];

export function classifyCommunicationFault(error: {
  status?: number;
  code?: string;
} | null | undefined): CommunicationFault {
  if (!error) return "OK";
  const status = error.status;
  const code = error.code || "";
  if (code === "network_error" || status === 0) return "API_UNREACHABLE";
  if (code === "timeout" || status === 408) return "API_TIMEOUT";
  if (
    code === "auth_bootstrap_pending" ||
    code === "missing_token" ||
    code === "AUTH_REQUIRED"
  ) {
    return "AUTH_REQUIRED";
  }
  if (
    status === 401 ||
    code === "unauthorized" ||
    code === "authentication_failed" ||
    code === "invalid_token" ||
    code === "AUTH_REFRESH"
  ) {
    return "AUTH_REFRESH";
  }
  if (
    status === 422 ||
    code === "request_validation_error" ||
    code === "CONTRACT_VALIDATION_ERROR"
  ) {
    return "CONTRACT_VALIDATION_ERROR";
  }
  if (status === 403 || code === "insufficient_role" || code === "forbidden") {
    return "FORBIDDEN";
  }
  if (status != null && status >= 500) return "SERVER_ERROR";
  return "SERVER_ERROR";
}

/** Communication faults are never a strategy NO_TRADE. */
export function isNoTradeFault(_fault: CommunicationFault): boolean {
  return false;
}

export function isAuthFault(fault: CommunicationFault): boolean {
  return fault === "AUTH_REQUIRED" || fault === "AUTH_REFRESH";
}
