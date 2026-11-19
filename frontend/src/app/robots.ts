import type { MetadataRoute } from "next";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: [
          "/",
          "/gold-trading-robot",
          "/ai-trading-assistant",
          "/strategies",
          "/pricing",
          "/live",
          "/contact",
          "/login",
          "/register",
          "/privacy",
          "/terms",
          "/risk-disclosure",
        ],
        disallow: [
          "/dashboard",
          "/admin",
          "/settings",
          "/profile",
          "/api/",
          "/auth/callback",
          "/book",
          "/research",
          "/counsel",
          "/journal",
          "/broker",
          "/brokers",
          "/inbox",
          "/get-started",
          "/organizations",
          "/ops",
          "/noc",
        ],
      },
    ],
    sitemap: `${SITE}/sitemap.xml`,
    host: SITE,
  };
}
