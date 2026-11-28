import type { MetadataRoute } from "next";
import { LEARN_PAGES, learnPath } from "@/lib/marketing/learn-catalog";
import { STRATEGIES } from "@/lib/seo/strategy-content";

const SITE =
  process.env.NEXT_PUBLIC_APP_URL?.replace(/\/$/, "") || "https://www.quantforg.com";

/**
 * Public, indexable routes only — never include authenticated desks.
 *
 * lastModified is omitted on purpose. Emitting `new Date()` made every crawl
 * look like a content change. Set lastModified only when a page’s content
 * actually changes.
 */
export default function sitemap(): MetadataRoute.Sitemap {
  const core: Array<[string, number, "daily" | "weekly" | "monthly"]> = [
    ["/", 1, "weekly"],
    ["/gold-trading-robot", 0.95, "weekly"],
    ["/mt5-expert-advisor", 0.85, "weekly"],
    ["/ai-trading-assistant", 0.9, "weekly"],
    ["/strategies", 0.9, "weekly"],
    ["/learn", 0.8, "monthly"],
    ["/pricing", 0.9, "weekly"],
    ["/live", 0.7, "daily"],
    ["/track-record", 0.8, "daily"],
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
      changeFrequency,
      priority,
    })),
    ...LEARN_PAGES.map((page) => ({
      url: `${SITE}${learnPath(page.slug)}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
    ...STRATEGIES.map((s) => ({
      url: `${SITE}/strategies/${s.slug}`,
      changeFrequency: "monthly" as const,
      priority: 0.7,
    })),
  ];
}
