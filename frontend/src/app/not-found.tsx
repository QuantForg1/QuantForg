import Link from "next/link";
import { BrandMark } from "@/components/brand/brand-logo";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <BrandMark size={48} />
      <h1 className="text-2xl font-semibold tracking-tight text-[var(--fg)]">Page not found</h1>
      <p className="max-w-md text-sm text-[var(--fg-muted)]">
        The route you requested does not exist in QuantForg.
      </p>
      <Link
        href="/terminal"
        className="qf-btn-primary inline-flex h-10 items-center justify-center rounded-[var(--radius-sm)] px-4 text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--ring)]"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
