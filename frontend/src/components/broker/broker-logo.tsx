"use client";

import { useState } from "react";
import { cn } from "@/lib/utils";

/** Official / brand mark for a documented MT5 broker. */
export function BrokerLogo({
  src,
  name,
  size = 28,
  className,
  rounded = "lg",
}: {
  src: string;
  name: string;
  size?: number;
  className?: string;
  rounded?: "md" | "lg" | "full";
}) {
  const [failed, setFailed] = useState(false);
  const radius =
    rounded === "full" ? "rounded-full" : rounded === "md" ? "rounded-md" : "rounded-lg";
  return (
    <span
      className={cn(
        "inline-flex shrink-0 items-center justify-center overflow-hidden border border-white/10 bg-white",
        radius,
        className,
      )}
      style={{ width: size, height: size, padding: Math.max(2, size * 0.08) }}
    >
      {failed ? (
        <span
          className="text-[10px] font-semibold uppercase tracking-wide text-[var(--fg-muted)]"
          aria-hidden
        >
          {name.slice(0, 2)}
        </span>
      ) : (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={src}
          alt={`${name} official logo`}
          width={size}
          height={size}
          className="h-full w-full object-contain"
          loading="lazy"
          decoding="async"
          onError={() => setFailed(true)}
        />
      )}
    </span>
  );
}

/** Official MetaTrader 5 mark (sourced from metatrader5.com). */
export function Mt5BrandMark({ size = 72, className }: { size?: number; className?: string }) {
  return (
    <span
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
    >
      <span
        className="absolute inset-[-12%] rounded-full opacity-50 blur-2xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,212,224,0.28) 0%, rgba(8,124,255,0.12) 48%, transparent 72%)",
        }}
        aria-hidden
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/brokers/metatrader5-logo.png"
        alt="MetaTrader 5 official logo"
        width={size}
        height={size}
        className="relative z-[1] h-full w-full rounded-2xl object-contain"
      />
    </span>
  );
}
