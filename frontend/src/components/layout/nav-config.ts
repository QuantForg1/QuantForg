import type { LucideIcon } from "lucide-react";
import {
  Activity,
  BarChart3,
  Bell,
  Bot,
  Briefcase,
  Building2,
  Cloud,
  CreditCard,
  FlaskConical,
  Gauge,
  History,
  LayoutDashboard,
  Layers3,
  LayoutTemplate,
  LifeBuoy,
  LineChart,
  ListOrdered,
  Newspaper,
  Settings,
  Shield,
  Rocket,
  Sparkles,
  Target,
  UserRound,
  Wallet,
  Waypoints,
} from "lucide-react";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
};

export type NavGroup = {
  title: string;
  items: NavItem[];
};

export const appNav: NavGroup[] = [
  {
    title: "Overview",
    items: [
      { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
      { href: "/intelligence", label: "Market Intelligence", icon: Sparkles },
      { href: "/portfolio", label: "Portfolio", icon: Briefcase },
      { href: "/performance", label: "Performance", icon: LineChart },
      { href: "/analytics", label: "Analytics", icon: BarChart3 },
      { href: "/wallet", label: "Wallet", icon: Wallet },
    ],
  },
  {
    title: "Trading",
    items: [
      { href: "/workspace", label: "Workspace", icon: LayoutTemplate },
      { href: "/execution", label: "Execution Center", icon: Target },
      { href: "/execution-intel", label: "Execution Intelligence", icon: Activity },
      { href: "/orders", label: "Orders", icon: ListOrdered },
      { href: "/positions", label: "Positions", icon: Layers3 },
      { href: "/history", label: "Trade History", icon: History },
      { href: "/paper", label: "Paper Trading", icon: Newspaper },
    ],
  },
  {
    title: "Research",
    items: [
      { href: "/strategy", label: "Strategy Builder", icon: Waypoints },
      { href: "/backtesting", label: "Backtesting", icon: FlaskConical },
      { href: "/walkforward", label: "Walk Forward", icon: Activity },
      { href: "/risk", label: "Risk Management", icon: Shield },
      { href: "/risk-lab", label: "Risk Laboratory", icon: FlaskConical },
      { href: "/ai", label: "AI Assistant", icon: Bot },
    ],
  },
  {
    title: "Connectivity",
    items: [
      { href: "/broker", label: "Broker Connection", icon: Building2 },
      { href: "/ops", label: "Operations", icon: Gauge },
      { href: "/cloud-ops", label: "Cloud Operations", icon: Cloud },
    ],
  },
  {
    title: "Account",
    items: [
      { href: "/get-started", label: "Get Started", icon: Rocket },
      { href: "/whats-new", label: "What's New", icon: Newspaper },
      { href: "/notifications", label: "Notifications", icon: Bell },
      { href: "/organizations", label: "Organizations", icon: CreditCard },
      { href: "/profile", label: "Profile", icon: UserRound },
      { href: "/settings", label: "Settings", icon: Settings },
      { href: "/support", label: "Support", icon: LifeBuoy },
    ],
  },
];

export const commandItems: NavItem[] = [
  ...appNav.flatMap((g) => g.items),
  { href: "/dashboard", label: "Risk score", icon: Gauge },
  { href: "/performance", label: "Drawdown", icon: Activity },
  { href: "/ai", label: "Explain strategy", icon: Sparkles },
];
