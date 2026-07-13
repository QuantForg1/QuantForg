import Link from "next/link";

export default function NotFound() {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-2xl font-semibold text-[var(--fg)]">Page not found</h1>
      <p className="max-w-md text-sm text-[var(--fg-muted)]">
        The route you requested does not exist in QuantForg.
      </p>
      <Link
        href="/dashboard"
        className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-[var(--accent-fg)]"
      >
        Back to dashboard
      </Link>
    </div>
  );
}
