import type { NextConfig } from "next";

const securityHeaders = [
  { key: "X-DNS-Prefetch-Control", value: "on" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  {
    key: "Permissions-Policy",
    value: "camera=(), microphone=(), geolocation=(), interest-cohort=()",
  },
  {
    key: "Content-Security-Policy",
    value: [
      "default-src 'self'",
      "base-uri 'self'",
      "form-action 'self'",
      "frame-ancestors 'none'",
      "object-src 'none'",
      "img-src 'self' data: blob: https:",
      "font-src 'self' data:",
      "style-src 'self' 'unsafe-inline'",
      "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
      "connect-src 'self' https: wss: http://127.0.0.1:* http://localhost:*",
      "worker-src 'self' blob:",
    ].join("; "),
  },
];

const nextConfig: NextConfig = {
  reactStrictMode: true,
  poweredByHeader: false,
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@tanstack/react-query",
      "recharts",
      "framer-motion",
      "lightweight-charts",
    ],
  },
  async redirects() {
    return [
      // /terminal was retired (2026-11-16). Old links land on the Dashboard,
      // which keeps the order ticket and robot status.
      { source: "/terminal", destination: "/dashboard", permanent: true },
      { source: "/terminal/:path*", destination: "/dashboard", permanent: true },
      { source: "/workspace", destination: "/dashboard", permanent: true },
      { source: "/execution", destination: "/dashboard", permanent: true },  // /execution/diagnostics stays
      { source: "/paper", destination: "/dashboard", permanent: false },
      // /symbols/:code is a page; the bare list lives on Markets.
      { source: "/symbols", destination: "/markets", permanent: false },
      { source: "/execution-intel", destination: "/executions", permanent: false },
      // Closed-order History desk retired; Book remains the trader ledger.
      { source: "/history", destination: "/book", permanent: false },

      // Portfolio OS — Book is canonical (Phase 3); /portfolio aliases Book
      { source: "/portfolio", destination: "/book", permanent: false },
      { source: "/wallet", destination: "/book", permanent: false },
      // Risk Center retired; robot desk owns the trader risk surface.
      { source: "/risk", destination: "/robot-control-center", permanent: false },
      { source: "/risk-center", destination: "/robot-control-center", permanent: false },
      { source: "/risk-lab", destination: "/allocation", permanent: false },

      // Strategies and Research are one desk. Legacy research URLs open it.
      { source: "/research", destination: "/strategy", permanent: false },
      { source: "/quant-studio", destination: "/strategy", permanent: false },
      { source: "/research-lab", destination: "/strategy", permanent: false },
      { source: "/backtesting", destination: "/strategy", permanent: false },
      { source: "/walkforward", destination: "/strategy", permanent: false },
      // /strategy and /intelligence stay on their product desks (reference rail).

      // Counsel / AI
      { source: "/quant-ai", destination: "/ai-signals", permanent: false },
      { source: "/decision-engine", destination: "/ai-signals", permanent: false },
      { source: "/ai", destination: "/ai-signals", permanent: false },
      { source: "/counsel", destination: "/ai-signals", permanent: false },

      // Journal / History
      { source: "/ecosystem", destination: "/journal", permanent: false },

      // Broker cluster
      { source: "/mt5", destination: "/broker", permanent: false },
      { source: "/brokers", destination: "/broker", permanent: false },
      { source: "/broker-connectivity", destination: "/gateway", permanent: false },
      { source: "/broker-compatibility", destination: "/broker", permanent: false },
      { source: "/broker-certification", destination: "/broker", permanent: false },

      // Inbox aliases
      { source: "/whats-new", destination: "/notifications", permanent: false },
      { source: "/inbox", destination: "/notifications", permanent: false },

      // System
      { source: "/cloud-ops", destination: "/gateway", permanent: false },
      { source: "/profile", destination: "/settings", permanent: false },
      { source: "/organizations", destination: "/settings", permanent: false },

      // Production workspace aliases (nav deep links)
      { source: "/oms", destination: "/executions", permanent: false },
      { source: "/multi-asset", destination: "/institutional-alpha", permanent: false },
      { source: "/trading-engine", destination: "/trading-kernel", permanent: false },
      { source: "/watchlist", destination: "/markets", permanent: false },
      { source: "/favorites", destination: "/symbol-management", permanent: false },
      { source: "/users", destination: "/admin/customer-ops", permanent: false },
      { source: "/system-health", destination: "/monitoring", permanent: false },
      { source: "/active-symbols", destination: "/symbol-management", permanent: false },
      { source: "/ai-learning", destination: "/live-learning-program", permanent: false },
      { source: "/signal-history", destination: "/signal-intelligence?tab=history", permanent: false },
      { source: "/heat-map", destination: "/signal-intelligence?tab=heatmap", permanent: false },
      { source: "/System/API%20Inspector", destination: "/api-inspector", permanent: false },
      { source: "/System/API Inspector", destination: "/api-inspector", permanent: false },
      { source: "/system/api-inspector", destination: "/api-inspector", permanent: false },
      { source: "/api-logs", destination: "/api-inspector", permanent: false },

      // Operator OS
      { source: "/trading-journal/replay", destination: "/ai-trade-replay", permanent: false },
      { source: "/ceo", destination: "/executive-dashboard", permanent: false },
      { source: "/operator", destination: "/operator-home", permanent: false },
      { source: "/coach", destination: "/ai-coach", permanent: false },
      { source: "/home", destination: "/mission-control", permanent: false },
      { source: "/production-home", destination: "/mission-control", permanent: false },
      { source: "/ceo-dashboard", destination: "/executive-home", permanent: false },
      { source: "/executive", destination: "/executive-home", permanent: false },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
  /**
   * Same-origin reverse proxy to the Railway API.
   * Browsers call `https://www.quantforg.com/qf-api/...` so flaky client DNS
   * to `*.up.railway.app` and cross-origin edge cases do not block auth.
   * Server-side / SSR can still use NEXT_PUBLIC_API_BASE_URL → Railway directly.
   */
  async rewrites() {
    const railwayOrigin =
      process.env.QUANTFORG_RAILWAY_ORIGIN?.replace(/\/$/, "") ||
      "https://quantforg-production.up.railway.app";
    return [
      {
        source: "/qf-api/:path*",
        destination: `${railwayOrigin}/:path*`,
      },
    ];
  },
};

export default nextConfig;
