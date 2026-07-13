import Link from "next/link";

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
    <div className="flex min-h-screen items-center justify-center px-4 py-10">
      <div className="w-full max-w-md">
        <Link href="/" className="mb-8 flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-[var(--accent)] font-bold text-[var(--accent-fg)]">
            Q
          </div>
          <span className="font-[family-name:var(--font-display)] text-lg">QuantForg</span>
        </Link>
        <div className="rounded-2xl border border-[var(--border)] bg-[var(--surface)]/80 p-6 shadow-[var(--shadow-card)] backdrop-blur-xl">
          <h1 className="font-[family-name:var(--font-display)] text-2xl tracking-tight">{title}</h1>
          <p className="mt-1 text-sm text-[var(--fg-muted)]">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
      </div>
    </div>
  );
}
