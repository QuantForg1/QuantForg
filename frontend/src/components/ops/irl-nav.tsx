"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { cn } from "@/lib/utils";

const LINKS = [
  { href: "/institutional-research-lab", label: "Dashboard" },
  { href: "/institutional-research-lab/experiments", label: "Experiments" },
  { href: "/institutional-research-lab/jobs", label: "Replay Jobs" },
  { href: "/institutional-research-lab/leaderboard", label: "Leaderboard" },
  { href: "/institutional-research-lab/reports", label: "Reports" },
  { href: "/institutional-research-lab/benchmark", label: "Benchmark" },
] as const;

export function IrlNav() {
  const pathname = usePathname();
  return (
    <nav className="mb-4 flex flex-wrap gap-2 border-b border-[var(--border)] pb-3">
      {LINKS.map((link) => {
        const active =
          link.href === "/institutional-research-lab"
            ? pathname === link.href
            : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={cn(
              "px-3 py-1.5 text-[12px] uppercase tracking-[0.1em]",
              active
                ? "border border-[var(--border-strong)] bg-[var(--surface-2)] text-[var(--fg)]"
                : "text-[var(--fg-muted)] hover:text-[var(--fg)]",
            )}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}
