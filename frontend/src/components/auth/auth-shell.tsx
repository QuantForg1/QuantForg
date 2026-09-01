import Link from "next/link";
import { BrandLogo } from "@/components/brand/brand-logo";

export function AuthShell({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle: string;
  children: React.ReactNode;
}) {
  return (
    <main
      id="main-content"
      className="relative flex min-h-screen items-center justify-center overflow-hidden px-4 py-12"
      tabIndex={-1}
    >
      <div
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_60%_45%_at_88%_8%,rgba(255,90,31,0.05),transparent_55%)]"
        aria-hidden
      />
      <div className="relative w-full max-w-[420px]">
        <Link href="/" className="mb-8 flex justify-center">
          <BrandLogo size={40} priority />
        </Link>
        <div className="rounded-[var(--radius-os)] border border-[var(--border)] bg-[var(--surface)] p-7 shadow-[var(--shadow-elevated)]">
          <h1 className="text-center font-[family-name:var(--font-display)] text-[1.45rem] font-semibold leading-tight tracking-tight text-[var(--fg)]">
            {title}
          </h1>
          <p className="mt-2 text-center text-sm text-[var(--fg-muted)]">{subtitle}</p>
          <div className="mt-7">{children}</div>
        </div>
      </div>
    </main>
  );
}
