import Image from "next/image";
import { cn } from "@/lib/utils";
import { BRAND_ASSETS } from "@/lib/brand/assets";

const VEIL = {
  soft: "bg-[linear-gradient(180deg,rgba(4,20,38,0.42)_0%,rgba(6,27,53,0.72)_52%,rgba(4,20,38,0.88)_100%),radial-gradient(ellipse_at_18%_12%,rgba(0,212,224,0.08),transparent_42%),radial-gradient(ellipse_at_82%_0%,rgba(8,124,255,0.08),transparent_48%)]",
  vivid:
    "bg-[linear-gradient(180deg,rgba(4,20,38,0.35)_0%,rgba(6,27,53,0.62)_48%,rgba(4,20,38,0.82)_100%),radial-gradient(ellipse_at_18%_12%,rgba(0,212,224,0.12),transparent_42%),radial-gradient(ellipse_at_82%_0%,rgba(8,124,255,0.1),transparent_48%)]",
} as const;

/**
 * Premium Blue Hybrid atmosphere for public + auth surfaces.
 * Official cinematic mountain under a soft navy veil — decorative only.
 */
export function MountainBackdrop({
  className,
  withCandles = false,
  intensity = "soft",
}: {
  className?: string;
  withCandles?: boolean;
  intensity?: keyof typeof VEIL;
}) {
  const photoOpacity = intensity === "vivid" ? "opacity-70" : "opacity-55";
  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      aria-hidden
    >
      <Image
        src={BRAND_ASSETS.mountain}
        alt=""
        fill
        priority={intensity === "vivid"}
        sizes="100vw"
        className={cn("object-cover object-[center_35%]", photoOpacity)}
      />
      <div className={cn("absolute inset-0", VEIL[intensity])} />
      {withCandles ? (
        <div className="absolute inset-y-[18%] right-[6%] hidden w-44 items-end gap-1 opacity-30 lg:flex">
          {Array.from({ length: 14 }, (_, i) => {
            const up = i % 2 === 0;
            const h = 28 + ((i * 17) % 64);
            return (
              <span
                key={i}
                className={cn(
                  "w-2 rounded-sm",
                  up ? "bg-[var(--success)]" : "bg-[var(--accent)]",
                )}
                style={{ height: `${h}%` }}
              />
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
