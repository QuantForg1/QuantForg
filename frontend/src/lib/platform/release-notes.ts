/** Curated in-app release notes for Closed Beta (static — no API change). */

export type ReleaseNote = {
  version: string;
  date: string;
  title: string;
  highlights: string[];
  links?: { label: string; href: string }[];
};

export const RELEASE_NOTES: ReleaseNote[] = [
  {
    version: "6.1.0-closed-beta",
    date: "2026-07-15",
    title: "Closed Beta V6.1 — platform complete",
    highlights: [
      "Feature-complete Closed Beta cut: Execution, Quant AI, Quant Studio, Decision Engine, Research Lab",
      "Live order_send remains off (EXECUTION_ENABLED=false in production)",
      "Invite-only cohort, Closed Beta banner, feedback widget, and issue reporting via Support",
      "Paper-first path: Get Started → paper trade → advisory desks",
      "Ops surfaces: /ops health & audit, /cloud-ops gateway heartbeats",
    ],
    links: [
      { label: "Get started", href: "/get-started" },
      { label: "Decision Engine", href: "/decision-engine" },
      { label: "Research Lab", href: "/research-lab" },
      { label: "Support / feedback", href: "/support#feedback" },
    ],
  },
  {
    version: "1.1.0-beta",
    date: "2026-07-13",
    title: "Closed Beta",
    highlights: [
      "MT5 Broker Connectivity Framework + ecosystem compatibility",
      "Broker certification workflow (real sessions only)",
      "Windows MT5 Gateway + Cloud Gateway Manager",
      "Strategy Engine, Portfolio Intelligence, Execution Intelligence",
      "Beta onboarding: get-started, tour, paper tutorial, release notes",
    ],
    links: [
      { label: "Get started", href: "/get-started" },
      { label: "Paper trading", href: "/paper" },
      { label: "Cloud operations", href: "/cloud-ops" },
    ],
  },
  {
    version: "1.0.0",
    date: "2026-07-12",
    title: "General Availability packaging",
    highlights: [
      "Durable Postgres Unit of Work factories",
      "EXECUTION_ENABLED remains false by default",
      "Committed poetry.lock for reproducible installs",
    ],
    links: [{ label: "Support", href: "/support" }],
  },
];

export function latestReleaseVersion(): string {
  return RELEASE_NOTES[0]?.version ?? "unknown";
}
