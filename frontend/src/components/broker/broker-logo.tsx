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
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={name}
        width={size}
        height={size}
        className="h-full w-full object-contain"
      />
    </span>
  );
}

export function Mt5BrandMark({ size = 72, className }: { size?: number; className?: string }) {
  return (
    <span
      className={cn("relative inline-flex items-center justify-center", className)}
      style={{ width: size, height: size }}
      aria-hidden
    >
      <span
        className="absolute inset-[-18%] rounded-full opacity-70 blur-xl"
        style={{
          background:
            "radial-gradient(circle, rgba(0,255,163,0.45) 0%, rgba(0,180,255,0.22) 45%, transparent 70%)",
        }}
      />
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src="/brand/brokers/mt5-mark.svg"
        alt=""
        width={size}
        height={size}
        className="relative z-[1] h-full w-full object-contain drop-shadow-[0_0_18px_rgba(0,212,224,0.45)]"
      />
    </span>
  );
}
