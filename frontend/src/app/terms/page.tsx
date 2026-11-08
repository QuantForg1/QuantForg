import type { Metadata } from "next";
import { LegalDoc } from "@/components/marketing/legal-doc";

export const metadata: Metadata = {
  title: "Terms of Service",
  description:
    "Terms governing use of the QuantForg trading technology platform and subscription access.",
  alternates: { canonical: "/terms" },
};

export default function TermsPage() {
  return (
    <LegalDoc title="Terms of Service" updated="8 November 2026">
      <p>
        These Terms govern access to QuantForg software and related websites. By creating an
        account or using the service, you agree to these Terms.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">The service</h2>
      <p>
        QuantForg is a trading technology platform. It provides software workflows for research,
        risk controls, broker connectivity, and related operations. QuantForg is not a broker,
        investment adviser, or guarantee of trading results.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Accounts & licenses</h2>
      <p>
        You must provide accurate registration information and keep credentials confidential.
        Subscription or license entitlements are granted only after verified payment confirmation
        and server-side provisioning. Client-side plan selection alone does not create paid access.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Subscriptions & crypto payments</h2>
      <ul className="list-disc space-y-2 pl-5">
        <li>Published plans: Starter ($49), Professional ($99), Premium ($199) per month in USD.</li>
        <li>
          Crypto invoices are processed by NOWPayments in LIVE production mode. Supported coins
          and networks are those enabled on the QuantForg merchant account.
        </li>
        <li>
          Automatic recurring crypto billing is not enabled unless separately announced. Renew by
          creating a new invoice before or after the paid period ends.
        </li>
        <li>
          A configurable grace period may apply after period end before paid entitlements expire.
          Temporary webhook delay alone does not immediately revoke access.
        </li>
        <li>
          Cancellation stops renewal intent; access typically continues until the paid period ends
          unless the account is suspended for abuse or risk.
        </li>
        <li>
          Refunds, if any, follow QuantForg’s then-current refund policy and payment-processor
          constraints. Browser redirects never prove payment.
        </li>
      </ul>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Acceptable use</h2>
      <ul className="list-disc space-y-2 pl-5">
        <li>Do not attempt to access another customer’s data or broker credentials.</li>
        <li>Do not circumvent authentication, authorization, or risk safeguards.</li>
        <li>Do not misuse the platform for unlawful activity.</li>
      </ul>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Broker relationships</h2>
      <p>
        Any MetaTrader 5 or broker relationship is between you and your broker. QuantForg does
        not claim unverified broker partnerships and does not replace broker agreements.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Disclaimer</h2>
      <p>
        Software is provided on an “as available” basis. Trading involves substantial risk of
        loss. See the Risk Disclosure. To the fullest extent permitted by law, QuantForg is not
        liable for trading losses, broker outages, or decisions you make using the software.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Changes</h2>
      <p>
        We may update these Terms. Material changes will be reflected on this page with an updated
        date. Continued use after changes constitutes acceptance where permitted by law.
      </p>
    </LegalDoc>
  );
}
