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
      // Flagship aliases
      { source: "/workspace", destination: "/terminal", permanent: false },
      { source: "/execution", destination: "/terminal", permanent: false },
      // Book desk
      { source: "/dashboard", destination: "/book", permanent: false },
      { source: "/portfolio", destination: "/book", permanent: false },
      { source: "/performance", destination: "/book", permanent: false },
      { source: "/analytics", destination: "/book", permanent: false },
      { source: "/wallet", destination: "/book", permanent: false },
      { source: "/risk", destination: "/book", permanent: false },
      { source: "/risk-lab", destination: "/book", permanent: false },
      // Research desk
      { source: "/quant-studio", destination: "/research", permanent: false },
      { source: "/research-lab", destination: "/research", permanent: false },
      { source: "/backtesting", destination: "/research", permanent: false },
      { source: "/walkforward", destination: "/research", permanent: false },
      { source: "/strategy", destination: "/research", permanent: false },
      // Counsel layer
      { source: "/quant-ai", destination: "/counsel", permanent: false },
      { source: "/decision-engine", destination: "/counsel", permanent: false },
      { source: "/intelligence", destination: "/counsel", permanent: false },
      { source: "/ai", destination: "/counsel", permanent: false },
      // Journal
      { source: "/ecosystem", destination: "/journal", permanent: false },
      // Broker cluster
      { source: "/mt5", destination: "/broker", permanent: false },
      { source: "/brokers", destination: "/broker", permanent: false },
      { source: "/broker-connectivity", destination: "/broker", permanent: false },
      { source: "/broker-compatibility", destination: "/broker", permanent: false },
      { source: "/broker-certification", destination: "/broker", permanent: false },
      // Trading fragments → terminal
      { source: "/orders", destination: "/terminal", permanent: false },
      { source: "/positions", destination: "/terminal", permanent: false },
      { source: "/history", destination: "/terminal", permanent: false },
      { source: "/execution-intel", destination: "/terminal", permanent: false },
      { source: "/paper", destination: "/terminal", permanent: false },
      // Marketing / onboarding out of chrome
      { source: "/get-started", destination: "/terminal", permanent: false },
      { source: "/whats-new", destination: "/notifications", permanent: false },
      // Ops → settings (admin tooling not in trader rail)
      { source: "/ops", destination: "/settings", permanent: false },
      { source: "/cloud-ops", destination: "/settings", permanent: false },
      { source: "/profile", destination: "/settings", permanent: false },
      { source: "/organizations", destination: "/settings", permanent: false },
    ];
  },
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
