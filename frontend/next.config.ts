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
      // Terminal aliases
      { source: "/workspace", destination: "/terminal", permanent: false },
      { source: "/execution", destination: "/terminal", permanent: false },
      { source: "/paper", destination: "/terminal", permanent: false },
      { source: "/get-started", destination: "/terminal", permanent: false },
      { source: "/execution-intel", destination: "/executions", permanent: false },
      { source: "/history", destination: "/executions", permanent: false },

      // Portfolio OS (Book → Portfolio)
      { source: "/book", destination: "/portfolio", permanent: false },
      { source: "/dashboard", destination: "/portfolio", permanent: false },
      { source: "/wallet", destination: "/portfolio", permanent: false },
      { source: "/risk", destination: "/risk-center", permanent: false },
      { source: "/risk-lab", destination: "/allocation", permanent: false },

      // Research cluster (lab tools stay under Research)
      { source: "/quant-studio", destination: "/research", permanent: false },
      { source: "/research-lab", destination: "/research", permanent: false },
      { source: "/backtesting", destination: "/research", permanent: false },
      { source: "/walkforward", destination: "/research", permanent: false },
      { source: "/strategy", destination: "/research", permanent: false },

      // Counsel / AI
      { source: "/quant-ai", destination: "/ai-signals", permanent: false },
      { source: "/decision-engine", destination: "/ai-signals", permanent: false },
      { source: "/intelligence", destination: "/ai-signals", permanent: false },
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
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
