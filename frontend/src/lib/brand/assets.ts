/**
 * Central QuantForg brand asset paths (QF monogram + lockups).
 * Prefer these constants over hardcoded strings.
 */

export const BRAND_ASSETS = {
  /** Primary app mark (256 web-optimized). */
  mark: "/brand/quantforg-mark-256.png",
  /** High-resolution mark for watermarks / large display. */
  markHiRes: "/brand/quantforg-mark.png",
  /** Symbol-only (same QF monogram). */
  symbol: "/brand/quantforg-symbol-256.png",
  symbolHiRes: "/brand/quantforg-symbol.png",
  /** Compact / small-size optimized. */
  compact: "/brand/quantforg-compact.png",
  /** Horizontal lockups. */
  horizontalDark: "/brand/quantforg-logo-horizontal.png",
  horizontalLight: "/brand/quantforg-logo-horizontal-light.png",
  /** Background variants. */
  logoDark: "/brand/quantforg-logo-dark.png",
  logoLight: "/brand/quantforg-logo-light.png",
  logoMono: "/brand/quantforg-logo-mono.png",
  /** Social / PWA. */
  ogImage: "/og-image.png",
  favicon32: "/favicon-32x32.png",
  appleTouch: "/apple-touch-icon.png",
  icon192: "/icon-192.png",
  icon512: "/icon-512.png",
} as const;

export const BRAND_NAME = "QuantForg";
export const BRAND_TAGLINE = "Trading Technology Platform";
export const BRAND_ACCENT = "#00D4E0";
export const BRAND_CHARCOAL = "#111827";
