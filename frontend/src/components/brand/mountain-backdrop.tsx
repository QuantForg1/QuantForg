import { cn } from "@/lib/utils";

/**
 * Decorative charcoal / cyan atmosphere used on public + auth surfaces.
 * Pure CSS/SVG — no photographic asset, no fabricated market data.
 */
export function MountainBackdrop({
  className,
  withCandles = false,
}: {
  className?: string;
  withCandles?: boolean;
}) {
  return (
    <div
      className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)}
      aria-hidden
    >
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_18%_12%,rgba(0,212,224,0.14),transparent_42%),radial-gradient(ellipse_at_82%_0%,rgba(94,246,255,0.1),transparent_48%),linear-gradient(180deg,#151b23_0%,#111827_58%,#0d1219_100%)]" />
      <svg
        className="absolute inset-x-0 bottom-0 h-[48%] w-full opacity-90"
        viewBox="0 0 1440 420"
        preserveAspectRatio="none"
      >
        <defs>
          <linearGradient id="qf-mtn-a" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#283344" stopOpacity="0.95" />
            <stop offset="100%" stopColor="#111827" stopOpacity="1" />
          </linearGradient>
          <linearGradient id="qf-mtn-b" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#1a2330" stopOpacity="0.92" />
            <stop offset="100%" stopColor="#0d1219" stopOpacity="1" />
          </linearGradient>
          <linearGradient id="qf-mtn-glow" x1="0" y1="0" x2="1" y2="0">
            <stop offset="35%" stopColor="#00d4e0" stopOpacity="0" />
            <stop offset="50%" stopColor="#00d4e0" stopOpacity="0.28" />
            <stop offset="65%" stopColor="#00d4e0" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x="0" y="180" width="1440" height="40" fill="url(#qf-mtn-glow)" />
        <path
          d="M0 420V250L180 140l140 70 160-110 120 60 200-130 150 90 170-70 150 80 170-50V420Z"
          fill="url(#qf-mtn-a)"
        />
        <path
          d="M0 420V310l220 20 160-90 180 70 210-120 190 80 160-40 150 50 170-30V420Z"
          fill="url(#qf-mtn-b)"
        />
      </svg>
      {withCandles ? (
        <div className="absolute inset-y-[18%] right-[6%] hidden w-44 items-end gap-1 opacity-35 lg:flex">
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
