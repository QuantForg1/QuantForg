import type { Metadata } from "next";
import { LegalDoc } from "@/components/marketing/legal-doc";

export const metadata: Metadata = {
  title: "Risk Disclosure",
  description:
    "Important risk disclosure for QuantForg software users. Trading can result in loss of capital.",
  alternates: { canonical: "/risk-disclosure" },
};

export default function RiskDisclosurePage() {
  return (
    <LegalDoc title="Risk Disclosure" updated="8 November 2026">
      <p>
        Trading foreign exchange, CFDs, metals, and related instruments involves a high level of
        risk and may not be suitable for all persons. You can lose some or all of your capital.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">No performance promises</h2>
      <p>
        QuantForg does not promise profits, guaranteed returns, risk-free trading, or verified
        historical track records. Any market analysis, automation, or signal tooling is software
        functionality — not a prediction of future results.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Market and execution risks</h2>
      <ul className="list-disc space-y-2 pl-5">
        <li>Gold / XAUUSD and related markets can move quickly with high volatility.</li>
        <li>Leverage and margin can amplify losses as well as gains.</li>
        <li>Slippage, spread widening, liquidity gaps, and market gaps can affect fills.</li>
        <li>Broker execution rules, symbol mapping, and server clocks may differ.</li>
        <li>Internet, hosting, gateway, or terminal outages can interrupt trading.</li>
        <li>Automated execution can place, modify, or close orders without continuous manual review.</li>
        <li>Software defects or misconfiguration can produce unexpected behavior.</li>
      </ul>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Software vs outcomes</h2>
      <p>
        Platform features such as risk checks, stops, or automation can fail, be misconfigured, or
        be overridden by broker conditions, connectivity issues, or market gaps. Existing
        safeguards reduce certain operational risks; they do not eliminate market risk. QuantForg
        is trading software and technology — not a promise of investment returns.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Your responsibility</h2>
      <ul className="list-disc space-y-2 pl-5">
        <li>Understand the products you trade and the broker terms that apply to you.</li>
        <li>Only risk capital you can afford to lose.</li>
        <li>Review positions, balances, and execution reports from your broker as the source of truth.</li>
        <li>Connecting a broker account and enabling live trading remain your decisions.</li>
      </ul>
      <p className="text-sm text-[var(--fg-muted)]">
        This disclosure is product documentation, not a lawyer-reviewed legal opinion unless
        separately confirmed in writing by counsel.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Jurisdiction</h2>
      <p>
        You are responsible for complying with laws and regulations that apply to you. Nothing on
        the QuantForg website constitutes an offer where such an offer would be unlawful.
      </p>
    </LegalDoc>
  );
}
