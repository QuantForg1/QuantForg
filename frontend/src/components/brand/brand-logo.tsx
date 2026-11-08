import Image from "next/image";
import { cn } from "@/lib/utils";
import {
  BRAND_ASSETS,
  BRAND_CAPTION,
  BRAND_NAME,
  BRAND_TAGLINE,
} from "@/lib/brand/assets";

type BrandLogoProps = {
  className?: string;
  /** Mark size in px (square). */
  size?: number;
  /** Show wordmark next to mark. */
  wordmark?: boolean;
  /** Compact wordmark caption under name. Defaults to institutional caption. */
  caption?: string | false;
  priority?: boolean;
  /** Prefer compact mark for dense chrome. */
  compact?: boolean;
  /** Use opaque navy-backed mark (favicons / rare surfaces). */
  opaque?: boolean;
};

function transparentMarkSrc(size: number, compact: boolean, hiRes: boolean) {
  if (compact) return BRAND_ASSETS.compactTransparent;
  if (hiRes || size > 256) return BRAND_ASSETS.markTransparent;
  return BRAND_ASSETS.markTransparentUi;
}

function opaqueMarkSrc(compact: boolean) {
  return compact ? BRAND_ASSETS.compact : BRAND_ASSETS.mark;
}

const MARK_SHADOW =
  "drop-shadow-[0_2px_12px_rgba(0,212,224,0.35)] drop-shadow-[0_1px_4px_rgba(2,12,28,0.45)]";

/**
 * Official QuantForg QF brand mark + optional wordmark.
 * Visual-only; no routing or auth behavior.
 */
export function BrandLogo({
  className,
  size = 32,
  wordmark = true,
  caption = BRAND_CAPTION,
  priority = false,
  compact = false,
  opaque = false,
}: BrandLogoProps) {
  const src = opaque
    ? opaqueMarkSrc(compact)
    : transparentMarkSrc(size, compact, false);
  const captionText = caption === false ? null : caption;
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Image
        src={src}
        alt={BRAND_NAME}
        width={size}
        height={size}
        className={cn("shrink-0 object-contain", !opaque && MARK_SHADOW)}
        priority={priority}
      />
      {wordmark ? (
        <span className="min-w-0">
          <span className="block truncate text-[0.95rem] font-semibold tracking-tight text-[var(--fg)]">
            {BRAND_NAME}
          </span>
          {captionText ? (
            <span className="qf-caption block truncate">{captionText}</span>
          ) : null}
        </span>
      ) : (
        <span className="sr-only">{BRAND_NAME}</span>
      )}
    </span>
  );
}

export function BrandMark({
  className,
  size = 32,
  priority = false,
  hiRes = false,
  compact = false,
  opaque = false,
}: {
  className?: string;
  size?: number;
  priority?: boolean;
  /** Use full-resolution mark for large decorative watermarks. */
  hiRes?: boolean;
  compact?: boolean;
  opaque?: boolean;
}) {
  const src = opaque
    ? compact
      ? BRAND_ASSETS.compact
      : hiRes || size > 128
        ? BRAND_ASSETS.markHiRes
        : BRAND_ASSETS.mark
    : transparentMarkSrc(size, compact, hiRes || size > 128);
  return (
    <Image
      src={src}
      alt={BRAND_NAME}
      width={size}
      height={size}
      className={cn("shrink-0 object-contain", !opaque && MARK_SHADOW, className)}
      priority={priority}
    />
  );
}

/** Horizontal lockup for marketing headers / emails. */
export function BrandLockup({
  className,
  variant = "dark",
  width = 220,
  height = 64,
  priority = false,
}: {
  className?: string;
  variant?: "dark" | "light";
  width?: number;
  height?: number;
  priority?: boolean;
}) {
  const src =
    variant === "light" ? BRAND_ASSETS.horizontalLight : BRAND_ASSETS.horizontalDark;
  return (
    <Image
      src={src}
      alt={`${BRAND_NAME} — ${BRAND_TAGLINE}`}
      width={width}
      height={height}
      className={cn("object-contain", className)}
      priority={priority}
    />
  );
}
