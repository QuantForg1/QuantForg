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
