import Image from "next/image";
import { cn } from "@/lib/utils";

/** Official RC4 mark — transparent web-optimized PNG. */
const MARK_SRC = "/brand/quantforg-mark-256.png";
const MARK_HIRES = "/brand/quantforg-mark.png";

type BrandLogoProps = {
  className?: string;
  /** Mark size in px (square). */
  size?: number;
  /** Show wordmark next to mark. */
  wordmark?: boolean;
  /** Compact wordmark caption under name. */
  caption?: string;
  priority?: boolean;
};

/**
 * RC4 QuantForg brand mark — official logo asset.
 * Visual-only; no routing or auth behavior.
 */
export function BrandLogo({
  className,
  size = 32,
  wordmark = true,
  caption,
  priority = false,
}: BrandLogoProps) {
  return (
    <span className={cn("inline-flex items-center gap-2.5", className)}>
      <Image
        src={MARK_SRC}
        alt="QuantForg"
        width={size}
        height={size}
        className="shrink-0 object-contain"
        priority={priority}
      />
      {wordmark ? (
        <span className="min-w-0">
          <span className="block truncate text-[0.95rem] font-semibold tracking-tight text-[var(--fg)]">
            QuantForg
          </span>
          {caption ? (
            <span className="qf-caption block truncate">{caption}</span>
          ) : null}
        </span>
      ) : (
        <span className="sr-only">QuantForg</span>
      )}
    </span>
  );
}

export function BrandMark({
  className,
  size = 32,
  priority = false,
  hiRes = false,
}: {
  className?: string;
  size?: number;
  priority?: boolean;
  /** Use full-resolution mark for large decorative watermarks. */
  hiRes?: boolean;
}) {
  return (
    <Image
      src={hiRes || size > 128 ? MARK_HIRES : MARK_SRC}
      alt="QuantForg"
      width={size}
      height={size}
      className={cn("shrink-0 object-contain", className)}
      priority={priority}
    />
  );
}
