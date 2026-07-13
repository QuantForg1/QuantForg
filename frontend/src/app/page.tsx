import Link from "next/link";

const features = [
  {
    title: "Live portfolio sync",
    body: "Positions, equity, and exposure synchronized from your MT5 terminal — read-first, execution gated.",
  },
  {
    title: "Risk before fill",
    body: "Pre-trade checks, SL/TP validation, and policy gates before any live order path is enabled.",
  },
  {
    title: "Research loop",
    body: "Strategy evaluation, backtests, walk-forward, and paper trading in one workspace.",
  },
  {
    title: "AI workspace",
    body: "Explain strategies, surface portfolio insights, and accelerate operator decisions.",
  },
];

const btn =
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--accent)] focus-visible:ring-offset-2 focus-visible:ring-offset-[var(--bg)]";
const btnPrimary = `${btn} h-11 px-6 bg-[var(--accent)] text-[var(--accent-fg)] hover:brightness-110 shadow-[0_0_0_1px_rgba(45,212,191,0.25)]`;
const btnSecondary = `${btn} h-11 px-6 bg-[var(--surface-2)] text-[var(--fg)] border border-[var(--border)] hover:bg-[var(--surface-3)]`;
const btnGhost = `${btn} h-10 px-4 text-[var(--fg-muted)] hover:bg-[var(--surface-2)] hover:text-[var(--fg)]`;

export default function LandingPage() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex w-full max-w-6xl items-center justify-between px-6 py-6">
        <div className="flex items-center gap-2">
          <div
            className="flex h-9 w-9 items-center justify-center rounded-lg bg-[var(--accent)] font-bold text-[var(--accent-fg)]"
            aria-hidden
          >
            Q
          </div>
          <span className="font-[family-name:var(--font-display)] text-lg tracking-tight">
            QuantForg
          </span>
        </div>
        <nav className="flex items-center gap-2" aria-label="Primary">
          <Link href="/login" className={btnGhost}>
            Sign in
          </Link>
          <Link href="/register" className={btnPrimary}>
            Open terminal
          </Link>
        </nav>
      </header>

      <main>
        <section className="relative mx-auto grid min-h-[78vh] w-full max-w-6xl items-center gap-10 px-6 pb-20 pt-8 lg:grid-cols-[1.1fr_0.9fr]">
          <div className="qf-fade-in">
            <p className="mb-4 text-sm font-medium tracking-[0.18em] text-[var(--accent)] uppercase">
              QuantForg
            </p>
            <h1 className="font-[family-name:var(--font-display)] text-4xl leading-[1.05] tracking-tight text-[var(--fg)] sm:text-5xl lg:text-6xl">
              The institutional trading terminal for operators who demand clarity.
            </h1>
            <p className="mt-5 max-w-xl text-base text-[var(--fg-muted)] sm:text-lg">
              Portfolio, risk, MT5 connectivity, research, and execution controls —
              designed like a product, measured like a desk.
            </p>
            <div className="mt-8 flex flex-wrap gap-3">
              <Link href="/register" className={btnPrimary}>
                Start free
              </Link>
              <Link href="/login" className={btnSecondary}>
                Sign in to workspace
              </Link>
            </div>
          </div>

          <div className="qf-fade-in relative overflow-hidden rounded-2xl border border-[var(--border)] bg-[var(--surface)]/70 p-5 shadow-[var(--shadow-card)] [animation-delay:120ms]">
            <div className="absolute inset-0 bg-[radial-gradient(circle_at_top_right,rgba(45,212,191,0.18),transparent_45%)]" />
            <div className="relative space-y-4">
              <div className="flex items-center justify-between">
                <p className="text-sm text-[var(--fg-muted)]">Equity curve</p>
                <p className="tabular text-sm text-[var(--success)]">+12.4%</p>
              </div>
              <svg
                viewBox="0 0 400 160"
                className="h-40 w-full"
                role="img"
                aria-label="Illustrative equity curve trending upward"
              >
                <defs>
                  <linearGradient id="eq" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stopColor="rgba(45,212,191,0.45)" />
                    <stop offset="100%" stopColor="rgba(45,212,191,0)" />
                  </linearGradient>
                </defs>
                <path
                  d="M0,120 C40,110 70,130 110,90 C150,50 180,70 220,55 C270,35 300,60 340,40 C370,28 390,35 400,30 L400,160 L0,160 Z"
                  fill="url(#eq)"
                />
                <path
                  d="M0,120 C40,110 70,130 110,90 C150,50 180,70 220,55 C270,35 300,60 340,40 C370,28 390,35 400,30"
                  fill="none"
                  stroke="#2dd4bf"
                  strokeWidth="2.5"
                />
              </svg>
              <div className="grid grid-cols-3 gap-3">
                {[
                  ["Balance", "$124,820"],
                  ["Exposure", "38%"],
                  ["Risk", "Low"],
                ].map(([k, v]) => (
                  <div
                    key={k}
                    className="rounded-lg border border-[var(--border)] bg-[var(--bg-elevated)]/60 p-3"
                  >
                    <p className="text-[11px] text-[var(--fg-subtle)]">{k}</p>
                    <p className="tabular mt-1 text-sm font-semibold">{v}</p>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </section>

        <section
          className="mx-auto grid w-full max-w-6xl gap-4 px-6 pb-24 sm:grid-cols-2 lg:grid-cols-4"
          aria-label="Product capabilities"
        >
          {features.map((f) => (
            <div
              key={f.title}
              className="rounded-xl border border-[var(--border)] bg-[var(--surface)]/60 p-5"
            >
              <h2 className="text-base font-semibold">{f.title}</h2>
              <p className="mt-2 text-sm text-[var(--fg-muted)]">{f.body}</p>
            </div>
          ))}
        </section>
      </main>
    </div>
  );
}
