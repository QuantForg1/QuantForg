import { cn } from "@/lib/utils";

/** Official Weltrade mark for Broker Accounts and marketing surfaces. */
export function WeltradeLogo({
  className,
  size = 40,
  variant = "mark",
}: {
  className?: string;
  size?: number;
  variant?: "mark" | "wordmark";
}) {
  const src =
    variant === "wordmark"
      ? "/brand/brokers/weltrade-logo.png"
      : "/brand/brokers/weltrade-mark.png";
  return (
    <span
      className={cn(
        "inline-flex items-center justify-center overflow-hidden rounded-xl border border-[var(--border)] bg-white",
        className,
      )}
      style={{ width: size, height: size, padding: Math.max(4, size * 0.12) }}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt="Weltrade"
        width={size}
        height={size}
        className="h-full w-full object-contain"
      />
    </span>
  );
}
