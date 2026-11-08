import type { MetadataRoute } from "next";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: ["/", "/pricing", "/contact", "/login", "/register", "/privacy", "/terms", "/risk-disclosure"],
        disallow: [
          "/dashboard",
          "/terminal",
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
