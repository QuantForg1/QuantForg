"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { pricingBtnPrimary } from "@/components/pricing/marketing-chrome";

/**
 * Floating purchase CTA — appears after scrolling past the hero price card.
 */
export function StickyPurchaseBar() {
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    const onScroll = () => {
      const hero = document.getElementById("license");
      if (!hero) {
        setVisible(window.scrollY > 480);
        return;
      }
      const bottom = hero.getBoundingClientRect().bottom;
      setVisible(bottom < 0);
    };
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div
      className={`qf-sticky-purchase fixed inset-x-0 bottom-0 z-50 px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-2 transition-all duration-[var(--duration-os)] ease-[var(--ease-os-out)] sm:px-6 ${
        visible
          ? "pointer-events-auto translate-y-0 opacity-100"
          : "pointer-events-none translate-y-4 opacity-0"
      }`}
      aria-hidden={!visible}
    >
      <div className="mx-auto flex max-w-3xl items-center gap-3 rounded-2xl border border-[var(--border-strong)] bg-[var(--bg-elevated)]/95 px-4 py-3 shadow-[var(--shadow-elevated)] backdrop-blur-md sm:gap-5 sm:px-5">
        <div className="min-w-0 flex-1">
          <p className="truncate text-xs font-medium uppercase tracking-[0.12em] text-[var(--accent)] sm:text-[0.7rem]">
            Lifetime License
          </p>
          <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 gap-y-0">
            <span className="font-[family-name:var(--font-display)] text-xl font-semibold tracking-tight sm:text-2xl">
              $2,499
            </span>
            <span className="text-xs text-[var(--fg-muted)] sm:text-sm">One-Time Payment</span>
          </p>
        </div>
        <Link
          href="/purchase"
          className={`${pricingBtnPrimary} h-11 shrink-0 px-4 text-sm sm:px-6`}
          tabIndex={visible ? 0 : -1}
        >
          Get Lifetime Access
        </Link>
      </div>
    </div>
  );
}
