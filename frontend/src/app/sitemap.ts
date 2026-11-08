import type { MetadataRoute } from "next";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

/** Public, indexable routes only — never include authenticated desks. */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const paths = [
    "/",
    "/pricing",
    "/contact",
    "/login",
    "/register",
    "/privacy",
    "/terms",
    "/risk-disclosure",
  ] as const;

  return paths.map((path) => ({
    url: `${SITE}${path === "/" ? "" : path}`,
    lastModified: now,
    changeFrequency: path === "/" || path === "/pricing" ? "weekly" : "monthly",
    priority: path === "/" ? 1 : path === "/pricing" ? 0.9 : 0.6,
  }));
}
