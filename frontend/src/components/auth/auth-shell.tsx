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
        className="pointer-events-none absolute inset-0 bg-[radial-gradient(ellipse_70%_55%_at_85%_40%,rgba(0,212,224,0.12),transparent_58%)]"
        aria-hidden
      />
      <div className="relative w-full max-w-[420px]">
        <Link href="/" className="mb-8 flex justify-center">
          <BrandLogo size={40} priority />
        </Link>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)]/90 p-7 shadow-[var(--shadow-elevated)] backdrop-blur-sm">
          <h1 className="text-center font-[family-name:var(--font-display)] text-[1.65rem] font-semibold leading-tight tracking-tight text-[var(--fg)]">
            {title}
          </h1>
          <p className="mt-2 text-center text-sm text-[var(--fg-muted)]">{subtitle}</p>
          <div className="mt-7">{children}</div>
        </div>
      </div>
    </main>
  );
}
