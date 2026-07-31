import Link from "next/link";
import { CheckCircle2 } from "lucide-react";
import { BrandMark } from "@/components/brand/brand-logo";
import {
  PricingFooter,
  PricingHeader,
  pricingBtnPrimary,
  pricingBtnSecondary,
} from "@/components/pricing/marketing-chrome";

export default function ContactSuccessPage() {
  return (
    <div className="min-h-screen overflow-x-clip">
      <PricingHeader active="contact" />

      <main
        id="main-content"
        className="mx-auto flex w-full max-w-xl flex-col items-center px-4 pb-24 pt-10 sm:px-6"
        tabIndex={-1}
      >
        <div className="qf-fade-in qf-glass-card relative w-full overflow-hidden border-[var(--accent)]/25 p-8 text-center sm:p-12">
          <div
            className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top,rgba(0,212,224,0.18),transparent_55%)]"
            aria-hidden
          />
          <div className="relative">
            <div className="qf-success-ring mx-auto flex h-20 w-20 items-center justify-center rounded-full bg-[var(--accent-soft)] text-[var(--accent)]">
              <CheckCircle2 className="h-10 w-10" strokeWidth={1.5} aria-hidden />
            </div>
            <div className="mx-auto mt-6">
              <BrandMark size={56} priority />
            </div>
            <h1 className="mt-6 font-[family-name:var(--font-display)] text-3xl tracking-tight sm:text-4xl">
              Request Submitted
            </h1>
            <p className="mt-3 text-base text-[var(--fg-muted)]">
              Thank you for contacting QuantForg.
            </p>
            <p className="mt-4 text-sm leading-relaxed text-[var(--fg-muted)]">
              Our team will review your request. If approved, we will contact you with payment
              instructions and create your account after payment verification.
            </p>
            <div className="mt-8 flex flex-col gap-3 sm:flex-row">
              <Link href="/contact" className={`${pricingBtnPrimary} h-11 flex-1`}>
                Contact Support
              </Link>
              <Link href="/" className={`${pricingBtnSecondary} h-11 flex-1`}>
                Back to Home
              </Link>
            </div>
          </div>
        </div>
      </main>

      <PricingFooter />
    </div>
  );
}
