import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  ArrowUpFromLine,
  BadgeCheck,
  BarChart3,
  Beaker,
  Bell,
  BookOpen,
  Bot,
  Brain,
  Briefcase,
  Building2,
  Cable,
  Calendar,
  CalendarClock,
  CandlestickChart,
  ClipboardCheck,
  Coins,
  Crosshair,
  Database,
  FileText,
  FileLock2,
  FlaskConical,
  Flame,
  Gauge,
  GitCompare,
  GraduationCap,
  HeartPulse,
  History,
  Keyboard,
  Layers3,
  LayoutTemplate,
  Library,
  LineChart,
  ListOrdered,
  MessageSquareWarning,
  Network,
  NotebookPen,
  PieChart,
  Radar,
  Repeat,
  Scale,
  ScanSearch,
  Settings,
  Shield,
  ShieldCheck,
  Sparkles,
  Store,
  Target,
  Timer,
  Workflow,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Short job description for command palette */
  hint?: string;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export type PrimaryNavItem = NavItem & {
  /** Path prefixes that count as active for this desk (beyond href). */
  match?: string[];
  /** ⌘N desk jump hint shown in rail tooltip */
  shortcut?: string;
  /**
   * Bloomberg-style section title. Rendered when it changes from the
   * previous item (expanded rail only).
   */
  section?:
    | "Trading"
    | "Execution"
    | "Signals"
    | "Portfolio"
    | "Market"
    | "Research"
    | "System";
};

/**
 * Production workspace rail — grouped navigation to existing surfaces.
 * ⌘1–8 remain on the eight primary desks.
 */
export const primaryRail: PrimaryNavItem[] = [
  {
    href: "/terminal",
    label: "Terminal",
    icon: LayoutTemplate,
    hint: "Trade — chart · watchlist · ticket",
    match: ["/terminal", "/workspace", "/execution"],
    shortcut: "1",
    section: "Trading",
  },
  {
    href: "/auto-trading",
    label: "Auto Trading",
    icon: Bot,
    hint: "Autonomous command center",
    match: ["/auto-trading"],
    section: "Trading",
  },
  {
    href: "/trading-kernel",
    label: "Trading Engine",
    icon: Gauge,
    hint: "Kernel · cycle · live gates",
    match: ["/trading-kernel", "/trading-engine"],
    section: "Trading",
  },
  {
    href: "/ai-scalping",
    label: "Scalping AI",
    icon: Crosshair,
    hint: "H1/M15/M5/M1 · quality gates",
    match: ["/ai-scalping", "/scalping-ai-v2"],
    section: "Trading",
  },
  {
    href: "/institutional-alpha",
    label: "Multi Asset",
    icon: Layers3,
    hint: "Multi-symbol ranking and handoff",
    match: ["/institutional-alpha", "/multi-asset"],
    section: "Trading",
  },
  {
    href: "/orders",
    label: "Orders",
    icon: ListOrdered,
    hint: "Working and pending orders",
    match: ["/orders"],
    section: "Execution",
  },
  {
    href: "/positions",
    label: "Positions",
    icon: Layers3,
    hint: "Open exposure blotter",
    match: ["/positions"],
    section: "Execution",
  },
  {
    href: "/executions",
    label: "Executions",
    icon: History,
    hint: "Fills and deal tape",
    match: ["/executions"],
    section: "Execution",
  },
  {
    href: "/oms",
    label: "OMS",
    icon: Workflow,
    hint: "Order management · execution tape",
    match: ["/oms"],
    section: "Execution",
  },
  {
    href: "/broker",
    label: "Broker",
    icon: Building2,
    hint: "Attach session · connectivity",
    match: ["/broker", "/gateway"],
    shortcut: "6",
    section: "Execution",
  },
  {
    href: "/signals",
    label: "Signal Center",
    icon: Radar,
    hint: "LIVE signal board",
    match: ["/signals"],
    section: "Signals",
  },
  {
    href: "/signal-intelligence",
    label: "Signal Intelligence",
    icon: Brain,
    hint: "History · outcomes · analytics",
    match: ["/signal-intelligence"],
    section: "Signals",
  },
  {
    href: "/signal-intelligence?tab=history",
    label: "Signal History",
    icon: History,
    hint: "Per-symbol signal timeline",
    match: ["/signal-intelligence"],
    section: "Signals",
  },
  {
    href: "/signal-intelligence?tab=outcomes",
    label: "Signal Outcomes",
    icon: ClipboardCheck,
    hint: "LIVE outcomes vs closes",
    match: ["/signal-intelligence"],
    section: "Signals",
  },
  {
    href: "/signal-intelligence?tab=heatmap",
    label: "Heat Map",
    icon: Flame,
    hint: "Session × symbol heat map",
    match: ["/signal-intelligence"],
    section: "Signals",
  },
  {
    href: "/signal-intelligence?tab=analytics",
    label: "Signal Analytics",
    icon: BarChart3,
    hint: "Aggregate quality and outcomes",
    match: ["/signal-intelligence"],
    section: "Signals",
  },
  {
    href: "/symbol-management",
    label: "Symbol Management",
    icon: Library,
    hint: "Universe · enable · favorites · sync",
    match: ["/symbol-management"],
    section: "Market",
  },
  {
    href: "/watchlist",
    label: "Watchlist",
    icon: CandlestickChart,
    hint: "Terminal market watch",
    match: ["/watchlist"],
    section: "Market",
  },
  {
    href: "/favorites",
    label: "Favorites",
    icon: Sparkles,
    hint: "Favorite symbols",
    match: ["/favorites"],
    section: "Market",
  },
  {
    href: "/symbol-management",
    label: "Active Symbols",
    icon: Activity,
    hint: "Enabled / scanner universe",
    match: ["/active-symbols"],
    section: "Market",
  },
  {
    href: "/market-scanner",
    label: "Scanner",
    icon: ScanSearch,
    hint: "Scan liquid markets",
    match: ["/market-scanner", "/screeners"],
    section: "Market",
  },
  {
    href: "/portfolio",
    label: "Portfolio",
    icon: Briefcase,
    hint: "Equity · health · book OS",
    match: ["/portfolio", "/book"],
    shortcut: "2",
    section: "Portfolio",
  },
  {
    href: "/exposure",
    label: "Exposure",
    icon: Target,
    hint: "Symbol and side exposure",
    match: ["/exposure"],
    section: "Portfolio",
  },
  {
    href: "/allocation",
    label: "Allocation",
    icon: PieChart,
    hint: "Capital allocation map",
    match: ["/allocation"],
    section: "Portfolio",
  },
  {
    href: "/performance",
    label: "Performance",
    icon: LineChart,
    hint: "Equity path and returns",
    match: ["/performance"],
    section: "Portfolio",
  },
  {
    href: "/risk-center",
    label: "Risk",
    icon: Shield,
    hint: "Pre-trade and session risk",
    match: ["/risk-center", "/risk"],
    section: "Portfolio",
  },
  {
    href: "/research",
    label: "Research",
    icon: FlaskConical,
    hint: "Idea → promote pipeline",
    match: ["/research", "/screeners"],
    shortcut: "3",
    section: "Research",
  },
  {
    href: "/strategy-diagnostics",
    label: "Strategy Diagnostics",
    icon: ScanSearch,
    hint: "Why NO_TRADE · confluence · MTF",
    match: ["/strategy-diagnostics"],
    section: "Research",
  },
  {
    href: "/continuous-validation",
    label: "Continuous Validation",
    icon: ClipboardCheck,
    hint: "CVF · drift · replay vs live",
    match: ["/continuous-validation"],
    section: "Research",
  },
  {
    href: "/live-learning-program",
    label: "AI Learning",
    icon: GraduationCap,
    hint: "Live learning program",
    match: ["/live-learning-program", "/ai-learning"],
    section: "Research",
  },
  {
    href: "/mission-control",
    label: "Mission Control",
    icon: Radar,
    hint: "Production status board",
    match: ["/mission-control"],
    section: "System",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    hint: "Profile, org, preferences",
    match: ["/settings", "/integrations", "/shortcuts"],
    shortcut: "8",
    section: "System",
  },
  {
    href: "/logs",
    label: "Logs",
    icon: FileText,
    hint: "Operational logs",
    match: ["/logs"],
    section: "System",
  },
  {
    href: "/monitoring",
    label: "System Health",
    icon: HeartPulse,
    hint: "Health · latency · uptime",
    match: ["/monitoring", "/institutional-observability", "/system-health"],
    shortcut: "7",
    section: "System",
  },
  {
    href: "/ai-signals",
    label: "Counsel",
    icon: Scale,
    hint: "Decide — advisory only",
    match: ["/ai-signals", "/counsel"],
    shortcut: "4",
    section: "System",
  },
  {
    href: "/journal",
    label: "Journal",
    icon: NotebookPen,
    hint: "Session memory and trade notes",
    match: ["/journal", "/trade-replay"],
    shortcut: "5",
    section: "System",
  },
];

export function isPrimaryActive(
  pathname: string,
  item: PrimaryNavItem,
  search = "",
): boolean {
  const hrefPath = item.href.split("?")[0] || item.href;
  const prefixes = item.match ?? [hrefPath];
  const pathOk = prefixes.some(
    (p) => pathname === p || pathname.startsWith(`${p}/`),
  );
  if (!pathOk) return false;

  const wantTab = (() => {
    const q = item.href.includes("?") ? item.href.slice(item.href.indexOf("?") + 1) : "";
    return new URLSearchParams(q).get("tab");
  })();
  const params = new URLSearchParams(
    search.startsWith("?") ? search.slice(1) : search,
  );
  const haveTab = params.get("tab");

  if (wantTab) {
    return haveTab === wantTab;
  }

  // Bare Signal Intelligence entry: active only on overview (no / default tab).
  if (hrefPath === "/signal-intelligence" && item.label === "Signal Intelligence") {
    return !haveTab || haveTab === "overview";
  }

  // Avoid highlighting every SI deep-link alias when on a tabbed SI page.
  if (
    hrefPath === "/signal-intelligence" &&
    haveTab &&
    haveTab !== "overview" &&
    item.label !== "Signal Intelligence"
  ) {
    return false;
  }

  return true;
}

/**
 * Full product catalog for command palette / deep links.
 * NOT rendered in the left rail. Routes stay alive; features stay reachable.
 * Terminal remains the sole live execution surface.
 */
export const appNav: NavGroup[] = [
  {
    title: "Trading",
    items: [
      {
        href: "/terminal",
        label: "Terminal",
        icon: LayoutTemplate,
        hint: "Chart · ticket · blotter",
      },
      {
        href: "/alerts",
        label: "Alerts",
        icon: Bell,
        hint: "Price and session alerts",
      },
      {
        href: "/orders",
        label: "Orders",
        icon: ListOrdered,
        hint: "Working and pending orders",
      },
      {
        href: "/positions",
        label: "Positions",
        icon: Layers3,
        hint: "Open exposure blotter",
      },
      {
        href: "/executions",
        label: "Executions",
        icon: History,
        hint: "Fills and deal tape",
      },
    ],
  },
  {
    title: "Portfolio",
    items: [
      {
        href: "/portfolio",
        label: "Portfolio",
        icon: Briefcase,
        hint: "Equity · health · book OS",
      },
      {
        href: "/performance",
        label: "Performance",
        icon: LineChart,
        hint: "Equity path and returns",
      },
      {
        href: "/exposure",
        label: "Exposure",
        icon: Target,
        hint: "Symbol and side exposure",
      },
      {
        href: "/risk-center",
        label: "Risk",
        icon: Shield,
        hint: "Pre-trade and session risk",
      },
      {
        href: "/allocation",
        label: "Allocation",
        icon: PieChart,
        hint: "Capital allocation map",
      },
    ],
  },
  {
    title: "Research",
    items: [
      {
        href: "/research",
        label: "Research",
        icon: FlaskConical,
        hint: "Idea → promote pipeline",
      },
      {
        href: "/institutional-research-lab",
        label: "Institutional Research Lab",
        icon: FlaskConical,
        hint: "IRL · experiments · replay · leaderboard · isolated",
      },
      {
        href: "/ai-quant-scientist",
        label: "AI Quant Scientist",
        icon: Brain,
        hint: "AQS · patterns · recommendations · explainability",
      },
      {
        href: "/ai-quant-copilot",
        label: "AI Quant Copilot",
        icon: Bot,
        hint: "AQC · ops Q&A · investigations · evidence",
      },
      {
        href: "/quant-knowledge-graph",
        label: "Knowledge Graph",
        icon: Workflow,
        hint: "QKG · nodes · relationships · evidence chains",
      },
      {
        href: "/execution-quality-suite",
        label: "Execution Quality",
        icon: Gauge,
        hint: "EQS · latency · slippage · fill quality",
      },
      {
        href: "/reliability-engineering-suite",
        label: "Reliability Suite",
        icon: HeartPulse,
        hint: "RES · health · recovery · failures",
      },
      {
        href: "/continuous-validation",
        label: "Continuous Validation",
        icon: ClipboardCheck,
        hint: "CVF · drift · replay vs live · evidence",
      },
      {
        href: "/institutional-simulation",
        label: "Simulation Engine",
        icon: Repeat,
        hint: "ISE · digital twin · monte carlo · stress",
      },
      {
        href: "/institutional-release",
        label: "Release Platform",
        icon: ArrowUpFromLine,
        hint: "IRDP · approval · rollback · release health",
      },
      {
        href: "/institutional-risk-analytics",
        label: "Risk Analytics",
        icon: Scale,
        hint: "IRAP · exposure · drawdown · VaR · stress",
      },
      {
        href: "/institutional-strategy-lifecycle",
        label: "Strategy Lifecycle",
        icon: Library,
        hint: "ISLM · registry · health · evidence · approval",
      },
      {
        href: "/institutional-experimentation",
        label: "Experimentation",
        icon: Beaker,
        hint: "IEP · hypothesis · compare · evidence · decision",
      },
      {
        href: "/institutional-control-plane",
        label: "Control Plane",
        icon: Network,
        hint: "ICP · executive health · timeline · dependencies",
      },
      {
        href: "/quantforg-certification",
        label: "Certification",
        icon: BadgeCheck,
        hint: "QCS · readiness · blockers · institutional gate",
      },
      {
        href: "/quantforg-strategy-marketplace",
        label: "Strategy Registry",
        icon: Store,
        hint: "QSMR · discovery · compare · evidence",
      },
      {
        href: "/quantforg-portfolio-manager",
        label: "Portfolio Manager",
        icon: PieChart,
        hint: "QPM · allocation · ranking · diversification",
      },
      {
        href: "/quantforg-operations-center",
        label: "Operations Center",
        icon: Radar,
        hint: "AOC · queue · recommendations · readiness",
      },
      {
        href: "/quantforg-event-mesh",
        label: "Event Mesh",
        icon: Cable,
        hint: "QEM · stream · timeline · correlation",
      },
      {
        href: "/quantforg-canonical-data",
        label: "Canonical Data",
        icon: Database,
        hint: "QCDM · schema · models · relationships",
      },
      {
        href: "/quantforg-decision-intelligence",
        label: "Decision Intelligence",
        icon: Scale,
        hint: "QDIE · recommendations · evidence · trade-offs",
      },
      {
        href: "/quantforg-strategy-factory",
        label: "Strategy Factory",
        icon: Workflow,
        hint: "QSF · pipeline · dossiers · human approvals",
      },
      {
        href: "/quantforg-paper-trading",
        label: "Paper Trading",
        icon: ClipboardCheck,
        hint: "QPTCM · campaigns · graduation · paper only",
      },
      {
        href: "/strategy-lab",
        label: "Strategy Lab",
        icon: Layers3,
        hint: "Validate · promote · lab only",
      },
      {
        href: "/threshold-performance-analysis",
        label: "Threshold Performance",
        icon: BarChart3,
        hint: "Offline Q×C gate matrix · research only",
      },
      {
        href: "/candidate-validation",
        label: "Candidate Validation",
        icon: GitCompare,
        hint: "Production 80/80 vs candidate 70/75",
      },
      {
        href: "/research-validation",
        label: "Validation Platform",
        icon: FlaskConical,
        hint: "Certify · rollback · release gates",
      },
      {
        href: "/intelligence-platform",
        label: "Intelligence",
        icon: BookOpen,
        hint: "Replay · review · governance",
      },
      {
        href: "/ai-signals",
        label: "AI Signals",
        icon: Sparkles,
        hint: "Decision intelligence signals",
      },
      {
        href: "/economic-calendar",
        label: "Economic Calendar",
        icon: Calendar,
        hint: "Macro event calendar",
      },
      {
        href: "/market-scanner",
        label: "Market Scanner",
        icon: Radar,
        hint: "Live market scan",
      },
      {
        href: "/screeners",
        label: "Screeners",
        icon: ScanSearch,
        hint: "Saved screen criteria",
      },
    ],
  },
  {
    title: "Operations",
    items: [
      {
        href: "/institutional-control-center",
        label: "Institutional Control Center",
        icon: LayoutTemplate,
        hint: "Executive cockpit · all subsystems · read-only",
      },
      {
        href: "/mission-control",
        label: "Mission Control",
        icon: LayoutTemplate,
        hint: "Executive platform supervision",
      },
      {
        href: "/trading-operations-center",
        label: "Ops Center",
        icon: ClipboardCheck,
        hint: "Daily brief · checklist · EOD reviews",
      },
      {
        href: "/audit-governance",
        label: "Governance",
        icon: Scale,
        hint: "Audit trail · forensics · compliance",
      },
      {
        href: "/institutional-data-warehouse",
        label: "Data Warehouse",
        icon: Database,
        hint: "Read-only analytics · dataset explorer",
      },
      {
        href: "/institutional-observability",
        label: "Observability",
        icon: Radar,
        hint: "Health · latency · uptime · alerts",
      },
      {
        href: "/production-readiness",
        label: "Readiness",
        icon: Shield,
        hint: "Production readiness program",
      },
      {
        href: "/monitoring",
        label: "Monitoring",
        icon: Gauge,
        hint: "Production ops · live execution",
      },
      {
        href: "/operations-runbook",
        label: "Operations Runbook",
        icon: BookOpen,
        hint: "State guidance · evidence · operator actions",
      },
      {
        href: "/auto-trading",
        label: "Auto Trading",
        icon: Bot,
        hint: "Autonomous command center",
      },
      {
        href: "/institutional-alpha",
        label: "Institutional Alpha",
        icon: ScanSearch,
        hint: "Multi-symbol ranking · correlation · adaptive risk",
      },
      {
        href: "/admin/noc",
        label: "NOC Command Center",
        icon: Gauge,
        hint: "Production ops · real telemetry · OWNER/ADMIN",
      },
      {
        href: "/symbol-management",
        label: "Symbol Management",
        icon: ListOrdered,
        hint: "Enable · disable · priority · trading universe",
      },
      {
        href: "/signals",
        label: "Signal Center",
        icon: Radar,
        hint: "LIVE AI signals · quality · confidence · detail",
      },
      {
        href: "/signal-intelligence",
        label: "Signal Intelligence",
        icon: BarChart3,
        hint: "History · outcomes · heat map · analytics · LIVE",
      },
      {
        href: "/admin/customer-ops",
        label: "Customer Operations",
        icon: Building2,
        hint: "Fleet · licenses · brokers · support · OWNER/ADMIN",
      },
      {
        href: "/admin/enterprise",
        label: "Enterprise Platform",
        icon: Building2,
        hint: "Orgs · RBAC · API keys · compliance · OWNER/ADMIN",
      },
      {
        href: "/admin/reliability",
        label: "Production Reliability",
        icon: Activity,
        hint: "SLA · incidents · health · security ops · OWNER/ADMIN",
      },
      {
        href: "/admin/continuous-improvement",
        label: "Continuous Improvement",
        icon: Activity,
        hint: "Validation · effectiveness · scorecard · OWNER/ADMIN",
      },
      {
        href: "/admin/live-trading-evidence",
        label: "Live Trading Evidence",
        icon: Activity,
        hint: "Trade archive · rejections · readiness · OWNER/ADMIN",
      },
      {
        href: "/production-validation",
        label: "Production Validation",
        icon: BadgeCheck,
        hint: "Live pipeline · evidence only · never trades",
      },
      {
        href: "/strategy-diagnostics",
        label: "Strategy Diagnostics",
        icon: ScanSearch,
        hint: "Why NO_TRADE · quality · confluence · MTF",
      },
      {
        href: "/live-execution-explain",
        label: "Live Execution Explain",
        icon: MessageSquareWarning,
        hint: "Decision card · first block · full trace",
      },
      {
        href: "/adaptive-opportunity",
        label: "Adaptive Opportunity",
        icon: Gauge,
        hint: "What is missing · opportunity meter · wait ETA",
      },
      {
        href: "/opportunity-timeline",
        label: "Opportunity Timeline",
        icon: LineChart,
        hint: "Last 100 evals · trends · approaching / weakening",
      },
      {
        href: "/strategy-intelligence-center",
        label: "Strategy Intelligence",
        icon: Brain,
        hint: "Closed trades · patterns · historical favorability",
      },
      {
        href: "/market-regime-intelligence",
        label: "Market Regime",
        icon: Layers3,
        hint: "TRENDING · BREAKOUT · vol · history · performance",
      },
      {
        href: "/portfolio-analytics",
        label: "Portfolio Analytics",
        icon: PieChart,
        hint: "Institutional dashboard · risk · health · reports",
      },
      {
        href: "/production-readiness-review",
        label: "Production Readiness Review",
        icon: ClipboardCheck,
        hint: "Institutional PRR · score · risks · checklist",
      },
      {
        href: "/micro-account-analyzer",
        label: "Micro Account Analyzer",
        icon: Coins,
        hint: "XAUUSD micro balances · broker min lot · eligibility",
      },
      {
        href: "/threshold-promotion",
        label: "Threshold Promotion",
        icon: ArrowUpFromLine,
        hint: "Promote 70/75 · rollback 80/80 · operator gated",
      },
      {
        href: "/experimental-threshold",
        label: "Experimental Threshold",
        icon: FlaskConical,
        hint: "EXPERIMENTAL_75 · Q75/C75 overlay · 100-eval report",
      },
      {
        href: "/production-reliability",
        label: "Production Reliability",
        icon: Activity,
        hint: "DNS · network incidents · reconnects · uptime",
      },
      {
        href: "/ai-validation",
        label: "AI Validation",
        icon: Brain,
        hint: "Shadow AI · strategy metrics · slippage · optimizer",
      },
      {
        href: "/performance-lab",
        label: "Performance Lab",
        icon: FlaskConical,
        hint: "Champion vs Challenger · calibration · replay",
      },
      {
        href: "/portfolio-intelligence",
        label: "Portfolio Intelligence",
        icon: PieChart,
        hint: "AI portfolio manager · allocation · risk budget",
      },
      {
        href: "/research-platform",
        label: "Research Platform",
        icon: FlaskConical,
        hint: "Experiments · backtests · models · promotions",
      },
      {
        href: "/rc1",
        label: "Release Candidate",
        icon: ShieldCheck,
        hint: "RC1 checklist · smoke · go-live score",
      },
      {
        href: "/ai-scalping",
        label: "AI Scalping",
        icon: Crosshair,
        hint: "H1/M15/M5/M1 · BUY/SELL quality gates",
      },
      {
        href: "/witness-health",
        label: "Witness Health",
        icon: HeartPulse,
        hint: "Auth vs execution · heartbeat continuity",
      },
      {
        href: "/production-burnin",
        label: "Burn-in Monitor",
        icon: Flame,
        hint: "Stability until first live fill",
      },
      {
        href: "/production-acceptance",
        label: "Production Acceptance",
        icon: ClipboardCheck,
        hint: "Read-only certification · first-fill evidence",
      },
      {
        href: "/automatic-production-acceptance",
        label: "Auto Acceptance",
        icon: BadgeCheck,
        hint: "Evidence-only gate · immutable report",
      },
      {
        href: "/production-acceptance-test",
        label: "Acceptance Test (PAT)",
        icon: FlaskConical,
        hint: "First live fill checklist · PDF/JSON export",
      },
      {
        href: "/first-execution-evidence",
        label: "First Execution Evidence",
        icon: FileLock2,
        hint: "Immutable write-once first live fill",
      },
      {
        href: "/production-acceptance-countdown",
        label: "Acceptance Countdown",
        icon: Timer,
        hint: "First eligible fill · session ETA · blockers",
      },
      {
        href: "/session-readiness",
        label: "Session Readiness",
        icon: CalendarClock,
        hint: "Allowed/blocked · execution window metrics",
      },
      {
        href: "/execution-timeline",
        label: "Execution Timeline",
        icon: ListOrdered,
        hint: "Chronological stages · blockers · filters",
      },
      {
        href: "/production-replay",
        label: "Production Replay",
        icon: Repeat,
        hint: "Simulation-only walk-forward replay · never trades",
      },
      {
        href: "/scalping-ai-v2",
        label: "Scalping AI V2",
        icon: Crosshair,
        hint: "XAUUSD scalp · never bypass Risk/Safety",
      },
      {
        href: "/adaptive-scalping-intelligence",
        label: "ASI",
        icon: Brain,
        hint: "Adaptive intelligence · explainable · advisory",
      },
      {
        href: "/institutional-edge-engine",
        label: "Edge Engine",
        icon: Gauge,
        hint: "Edge score · stability · institutional grade",
      },
      {
        href: "/alpha-factory",
        label: "Alpha Factory",
        icon: FlaskConical,
        hint: "Research lab · never touches production",
      },
      {
        href: "/institutional-validation-program",
        label: "Validation Program",
        icon: ClipboardCheck,
        hint: "IVP · read-only evidence · never trades",
      },
      {
        href: "/real-market-intelligence-platform",
        label: "Market Context",
        icon: Radar,
        hint: "RMIP · real-world context · never trades",
      },
      {
        href: "/live-learning-program",
        label: "Live Learning",
        icon: GraduationCap,
        hint: "LLP · evidence only · never auto-tunes",
      },
      {
        href: "/production-readiness-certification",
        label: "Readiness Cert",
        icon: BadgeCheck,
        hint: "PRC · certify only · human approval",
      },
      {
        href: "/integration-sprint-v1",
        label: "Integration Bus",
        icon: Cable,
        hint: "Read-only feeds · never trades",
      },
      {
        href: "/ai-robot",
        label: "AI Robot",
        icon: Shield,
        hint: "Robot V1 · capital preservation",
      },
      {
        href: "/institutional-decision",
        label: "AI Decision",
        icon: Scale,
        hint: "Institutional decision engine V1",
      },
      {
        href: "/decision-intelligence",
        label: "Decision Center",
        icon: Target,
        hint: "Final pre-execution decision gate",
      },
      {
        href: "/market-intelligence",
        label: "Market Intel",
        icon: Radar,
        hint: "Market Intelligence Engine V1",
      },
      {
        href: "/alpha-engine",
        label: "Alpha Engine",
        icon: CandlestickChart,
        hint: "Market quality before execution",
      },
      {
        href: "/trading-kernel",
        label: "Trading Kernel",
        icon: Layers3,
        hint: "Core OS · orchestrate · never bypass",
      },
      {
        href: "/multi-agent-ai",
        label: "Multi-Agent AI",
        icon: Bot,
        hint: "Agents collaborate before approval",
      },
      {
        href: "/trading-brain-v3",
        label: "Trading Brain V3",
        icon: Brain,
        hint: "Capital preservation orchestration",
      },
      {
        href: "/gateway",
        label: "Gateway",
        icon: Workflow,
        hint: "MT5 gateway control",
      },
      {
        href: "/broker",
        label: "Broker",
        icon: Building2,
        hint: "Connect · diagnose · settings",
      },
      {
        href: "/execution/diagnostics",
        label: "Execution Audit",
        icon: FileText,
        hint: "Validation · risk · MT5 audit",
      },
      {
        href: "/logs",
        label: "Logs",
        icon: BookOpen,
        hint: "Operational log stream",
      },
      {
        href: "/incidents",
        label: "Incidents",
        icon: AlertTriangle,
        hint: "Active and resolved incidents",
      },
    ],
  },
  {
    title: "History",
    items: [
      {
        href: "/journal",
        label: "Journal",
        icon: NotebookPen,
        hint: "Trade memory and notes",
      },
      {
        href: "/trade-replay",
        label: "Trade Replay",
        icon: CandlestickChart,
        hint: "Replay closed trades",
      },
      {
        href: "/analytics",
        label: "Analytics",
        icon: Activity,
        hint: "Win rate · expectancy · DD",
      },
      {
        href: "/performance-intelligence",
        label: "Performance IQ",
        icon: BarChart3,
        hint: "Sessions · regimes · signals · NO_TRADE",
      },
      {
        href: "/replay-evidence-lab",
        label: "Evidence Lab",
        icon: FlaskConical,
        hint: "Replay · counterfactual · confidence gates",
      },
      {
        href: "/reports",
        label: "Reports",
        icon: FileText,
        hint: "Exportable performance reports",
      },
    ],
  },
  {
    title: "System",
    items: [
      {
        href: "/settings",
        label: "Settings",
        icon: Settings,
        hint: "Profile, org, prefs",
      },
      {
        href: "/notifications",
        label: "Notifications",
        icon: Bell,
        hint: "Inbox and delivery",
      },
      {
        href: "/integrations",
        label: "Integrations",
        icon: Workflow,
        hint: "Connected services",
      },
      {
        href: "/shortcuts",
        label: "Keyboard Shortcuts",
        icon: Keyboard,
        hint: "Global and desk shortcuts",
      },
    ],
  },
];

/** Compact mobile bottom bar — thumb-first primary desks. */
export const mobileTabNav: NavItem[] = [
  {
    href: "/terminal",
    label: "Trade",
    icon: LayoutTemplate,
    hint: "Terminal",
  },
  {
    href: "/portfolio",
    label: "Book",
    icon: Briefcase,
    hint: "Book",
  },
  {
    href: "/research",
    label: "Research",
    icon: FlaskConical,
    hint: "Research",
  },
  {
    href: "/ai-signals",
    label: "Counsel",
    icon: Scale,
    hint: "Counsel",
  },
  {
    href: "/broker",
    label: "Broker",
    icon: Building2,
    hint: "Broker",
  },
];

/** Deduped catalog for ⌘K — every living route remains searchable. */
export const commandItems: NavItem[] = (() => {
  const map = new Map<string, NavItem>();
  for (const item of primaryRail) map.set(item.href, item);
  for (const g of appNav) {
    for (const item of g.items) map.set(item.href, item);
  }
  const extras: NavItem[] = [
    {
      href: "/counsel",
      label: "Counsel",
      icon: Scale,
      hint: "Decision intelligence (advise only)",
    },
    {
      href: "/auto-trading",
      label: "Auto Trading",
      icon: Sparkles,
      hint: "Operator auto-trade controls",
    },
    {
      href: "/ops",
      label: "Ops control",
      icon: Gauge,
      hint: "ITE control plane · kill switch",
    },
    {
      href: "/admin/noc",
      label: "NOC Command Center",
      icon: Gauge,
      hint: "Institutional production operations desk",
    },
  ];
  for (const item of extras) map.set(item.href, item);
  return [...map.values()];
})();

/** Flat list used by command palette page search. */
export const commandCatalog: NavItem[] = commandItems;
