/** Format Weltrade / GatewayMT5Client health diagnostics for UI copy. */

export function gatewayStatusLabel(health: Record<string, unknown>): string {
  const online = Boolean(
    health.gateway_online || health.gateway_reachable,
  );
  if (online) return "Gateway Online";

  const diagnostic = String(health.diagnostic || "").trim();
  if (diagnostic && diagnostic !== "ok" && diagnostic !== "Gateway Offline") {
    return diagnostic;
  }

  const detail = String(
    health.last_upstream_error ||
      health.upstream_error ||
      health.detail ||
      "",
  ).trim();
  if (!detail || detail === "ok") return "Gateway unreachable";

  const lower = detail.toLowerCase();
  if (lower.includes("invalid gateway token") || lower.includes("401")) {
    return "Invalid Gateway Token";
  }
  if (lower.includes("403")) return "403 Forbidden";
  if (lower.includes("404")) return "404 Endpoint";
  if (lower.includes("redirect loop") || lower.includes("too many redirects")) {
    return "Redirect loop";
  }
  if (lower.includes("non-json") || lower.includes("json parse")) {
    return "JSON parse error";
  }
  if (lower.includes("tls") || lower.includes("ssl") || lower.includes("certificate")) {
    return "TLS failure";
  }
  if (lower.includes("timeout")) {
    return lower.includes("cloudflare") || lower.includes("trycloudflare")
      ? "Cloudflare timeout"
      : "Gateway timeout";
  }
  if (lower.includes("connection refused") || lower.includes("refused")) {
    return "Gateway refused connection";
  }
  if (diagnostic) return diagnostic;
  return detail.slice(0, 120);
}

export function gatewayDiagnosticDetail(
  health: Record<string, unknown>,
): string {
  return String(
    health.last_upstream_error ||
      health.upstream_error ||
      health.detail ||
      "",
  ).trim();
}
