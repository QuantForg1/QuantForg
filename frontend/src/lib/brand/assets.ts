/**
 * Central QuantForg brand asset paths (QF monogram + lockups).
 * Prefer these constants over hardcoded strings.
 *
 * Visual source of truth: official Teal QF Finance / Market Trend logos.
 * Surfaces: Premium Blue Hybrid navy + logo-derived teal/cyan.
 */

export const BRAND_ASSETS = {
  /** Primary app mark (256 web-optimized). */
  mark: "/brand/quantforg-mark-256.png",
  /** High-resolution mark for watermarks / large display. */
  markHiRes: "/brand/quantforg-mark.png",
  /** Transparent mark for overlays. */
  markTransparent: "/brand/quantforg-mark-transparent.png",
  /** Web UI default — transparent mark without black tile. */
  markTransparentUi: "/brand/quantforg-mark-transparent-256.png",
  /** Symbol-only (same QF monogram). */
  symbol: "/brand/quantforg-symbol-256.png",
  symbolHiRes: "/brand/quantforg-symbol.png",
  symbolTransparent: "/brand/quantforg-symbol-transparent-256.png",
  /** Compact / small-size optimized. */
  compact: "/brand/quantforg-compact.png",
  compactTransparent: "/brand/quantforg-compact-transparent.png",
  /** Horizontal lockups. */
  horizontalDark: "/brand/quantforg-logo-horizontal.png",
  horizontalLight: "/brand/quantforg-logo-horizontal-light.png",
  /** Background variants. */
  logoDark: "/brand/quantforg-logo-dark.png",
  logoLight: "/brand/quantforg-logo-light.png",
  logoMono: "/brand/quantforg-logo-mono.png",
  /** Atmosphere. */
  mountain: "/brand/mountain-backdrop.jpg",
  /** Social / PWA / favicons. */
  ogImage: "/og-image.png",
  faviconSvg: "/favicon.svg",
  favicon32: "/favicon-32x32.png",
  favicon48: "/favicon-48x48.png",
  appleTouch: "/apple-touch-icon.png",
  icon192: "/icon-192.png",
  icon512: "/icon-512.png",
} as const;

export const BRAND_NAME = "QuantForg";
export const BRAND_TAGLINE = "Institutional AI Trading Platform";
export const BRAND_CAPTION = "Institutional Trading Intelligence";

/** Logo-derived cyan accent (official QF glow). */
export const BRAND_ACCENT = "#00D4E0";
/** Deeper teal sampled from the official QF stroke. */
export const BRAND_TEAL = "#00CAC0";
/** Premium Blue Hybrid deep navy (primary surface). */
export const BRAND_NAVY = "#061B35";
/** Primary institutional blue. */
export const BRAND_PRIMARY_BLUE = "#0756A8";
/** Electric blue highlight. */
export const BRAND_ELECTRIC = "#087CFF";

/** @deprecated Prefer BRAND_NAVY — kept for transitional imports. */
export const BRAND_CHARCOAL = BRAND_NAVY;
