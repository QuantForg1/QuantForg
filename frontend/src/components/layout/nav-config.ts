import type { LucideIcon } from "lucide-react";
import {
  Activity,
  AlertTriangle,
  BadgeCheck,
  BarChart3,
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
  Crosshair,
  Database,
  FileText,
  FileLock2,
  FlaskConical,
  Gauge,
  GraduationCap,
  History,
  Keyboard,
  Layers3,
  LayoutTemplate,
  LineChart,
  ListOrdered,
  NotebookPen,
  PieChart,
  Radar,
  Repeat,
  Scale,
  ScanSearch,
  Settings,
  Shield,
  Sparkles,
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

/**
 * QuantForg OS V3 — workspace information architecture.
 * Each route has one responsibility. Terminal remains the sole live execution surface.
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
        href: "/strategy-lab",
        label: "Strategy Lab",
        icon: Layers3,
        hint: "Validate · promote · lab only",
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
        href: "/auto-trading",
        label: "Auto Trading",
        icon: Bot,
        hint: "Autonomous command center",
      },
      {
        href: "/production-validation",
        label: "Production Validation",
        icon: BadgeCheck,
        hint: "Live pipeline · evidence only · never trades",
      },
      {
        href: "/production-reliability",
        label: "Production Reliability",
        icon: Activity,
        hint: "DNS · network incidents · reconnects · uptime",
      },
      {
        href: "/production-acceptance",
        label: "Production Acceptance",
        icon: ClipboardCheck,
        hint: "Read-only certification · first-fill evidence",
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

/** Compact mobile bottom bar — one-hand primary surfaces. */
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
    hint: "Portfolio",
  },
  {
    href: "/research",
    label: "Research",
    icon: FlaskConical,
    hint: "Research",
  },
  {
    href: "/journal",
    label: "Journal",
    icon: NotebookPen,
    hint: "Journal",
  },
  {
    href: "/broker",
    label: "Broker",
    icon: Building2,
    hint: "Broker",
  },
];

export const commandItems: NavItem[] = [
  ...appNav.flatMap((g) => g.items),
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
];
