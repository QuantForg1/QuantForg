import { SiteFooter } from "@/components/marketing/site-footer";
import { SiteHeader } from "@/components/marketing/site-header";

const btn =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[var(--radius-sm)] text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]";

export const pricingBtnPrimary = `${btn} qf-btn-primary h-11 px-6`;
export const pricingBtnSecondary = `${btn} h-11 px-6 border border-[var(--border-strong)] bg-transparent text-[var(--fg)] hover:bg-[var(--surface-2)]`;
export const pricingBtnGhost = `${btn} h-10 px-4 text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]`;
export const pricingBtnOutline = `${btn} h-10 px-4 border border-[var(--border)] text-[var(--fg)] hover:border-[var(--border-strong)] hover:bg-[var(--surface-2)]`;

export function PricingHeader({
  active = "pricing",
}: {
  active?: "home" | "pricing" | "purchase" | "contact";
}) {
  return <SiteHeader active={active} />;
}

export function PricingFooter() {
  return <SiteFooter />;
}
