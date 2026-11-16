/** Robot Control Center presentation helpers (state comes from the backend). */

export const ROBOT_ACTIONS = [
  "pause",
  "resume",
  "start",
  "stop",
  "emergency_stop",
] as const;
export type RobotAction = (typeof ROBOT_ACTIONS)[number];

export function robotStateLabel(state: string): string {
  switch (state) {
    case "RUNNING":
      return "Running";
    case "PAUSED":
      return "Paused";
    case "STOPPED":
      return "Stopped";
    case "EMERGENCY_STOPPED":
      return "Emergency stopped";
    default:
      return state || "Unknown";
  }
}

export function robotStateTone(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "RUNNING") return "success";
  if (state === "PAUSED" || state === "STOPPED") return "warning";
  if (state === "EMERGENCY_STOPPED") return "danger";
  return "neutral";
}

/** Verified connection states (backend evidence). Connected ≠ allowed to trade. */
export function connectionStateLabel(state: string): string {
  switch (state) {
    case "ROBOT_READY":
      return "Robot ready";
    case "CONNECTED":
      return "Connected · trade permission unknown";
    case "TRADING_PERMISSION_DISABLED":
      return "Connected · trading disabled by MT5";
    case "DEGRADED":
      return "Degraded";
    case "REQUIRES_USER_ACTION":
      return "Action required";
    case "NOT_CONNECTED":
      return "Not connected";
    case "UNAVAILABLE":
      return "Broker data unavailable · new entries blocked";
    default:
      return state || "Unknown";
  }
}

export function connectionStateTone(
  state: string,
): "success" | "warning" | "danger" | "neutral" {
  if (state === "ROBOT_READY") return "success";
  if (state === "CONNECTED" || state === "DEGRADED") return "warning";
  if (
    state === "TRADING_PERMISSION_DISABLED" ||
    state === "REQUIRES_USER_ACTION"
  )
    return "danger";
  return "neutral";
}
