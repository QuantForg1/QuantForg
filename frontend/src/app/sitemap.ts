import type { MetadataRoute } from "next";
import { STRATEGIES } from "@/lib/seo/strategy-content";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

/** Public, indexable routes only — never include authenticated desks. */
export default function sitemap(): MetadataRoute.Sitemap {
  const now = new Date();
  const core: Array<[string, number, "daily" | "weekly" | "monthly"]> = [
    ["/", 1, "weekly"],
    ["/gold-trading-robot", 0.95, "weekly"],
    ["/ai-trading-assistant", 0.9, "weekly"],
    ["/strategies", 0.9, "weekly"],
    ["/pricing", 0.9, "weekly"],
    ["/live", 0.7, "daily"],
    ["/register", 0.7, "monthly"],
    ["/contact", 0.5, "monthly"],
    ["/login", 0.4, "monthly"],
    ["/privacy", 0.3, "monthly"],
    ["/terms", 0.3, "monthly"],
    ["/risk-disclosure", 0.3, "monthly"],
  ];
  return [
    ...core.map(([path, priority, changeFrequency]) => ({
      url: `${SITE}${path === "/" ? "" : path}`,
      lastModified: now,
      changeFrequency,
      priority,
    })),
    ...STRATEGIES.map((s) => ({
      url: `${SITE}/strategies/${s.slug}`,
      lastModified: now,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}
