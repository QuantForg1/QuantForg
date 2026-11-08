import type { Metadata } from "next";
import { LegalDoc } from "@/components/marketing/legal-doc";

export const metadata: Metadata = {
  title: "Privacy Policy",
  description:
    "How QuantForg collects, uses, and protects account and platform data. Trading outcomes are not part of this policy.",
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

export default function PrivacyPage() {
  return (
    <LegalDoc title="Privacy Policy" updated="8 November 2026">
      <p>
        QuantForg (“we”, “us”) provides trading technology software. This policy explains how we
        handle information when you use quantforg.com and related authenticated workspaces.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Information we process</h2>
      <ul className="list-disc space-y-2 pl-5">
        <li>Account identifiers such as email, display name, and authentication metadata.</li>
        <li>Session and security events needed to keep signed-in access safe.</li>
        <li>
          Broker connection details you voluntarily provide to operate your own MetaTrader 5
          workflows. Credentials are handled through the existing secure infrastructure and are
          not meant to be shared across unrelated customers.
        </li>
        <li>
          Subscription and payment references for crypto invoices processed by NOWPayments (plan,
          amount, currency, invoice and payment identifiers, and payment status). We do not store
          full wallet private keys.
        </li>
        <li>Support messages and contact form submissions you send to us.</li>
        <li>
          Trading operational data generated while you use authenticated desks (for example
          positions and order history associated with your own broker session).
        </li>
      </ul>
      <h2 className="text-lg font-semibold text-[var(--fg)]">How we use information</h2>
      <p>
        We use account and operational data to authenticate users, provide the product, enforce
        authorization, operate risk and execution safeguards already in the platform, improve
        reliability, and communicate about service status or support.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Sharing</h2>
      <p>
        We do not sell personal information. Infrastructure processors (for example hosting,
        authentication, email delivery, and NOWPayments as the crypto payment processor) may
        process data solely to run QuantForg. We do not publish another customer’s MT5 account,
        positions, balances, or credentials. Cross-customer access is blocked by server-side
        authorization and Row Level Security where configured.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Cookies and sessions</h2>
      <p>
        We use session and authentication cookies or tokens required to keep you signed in and to
        protect the workspace. Analytics cookies are used only if explicitly enabled in a given
        deployment.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Retention & security</h2>
      <p>
        We retain account records while your account is active and as needed for security, legal,
        and operational continuity. Access controls and Row Level Security policies are designed
        so customers only reach their own protected resources server-side.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Your choices</h2>
      <p>
        You may request account corrections or deletion subject to legitimate retention needs by
        contacting support. Password reset and session controls are available in the product where
        authentication is enabled.
      </p>
      <h2 className="text-lg font-semibold text-[var(--fg)]">Contact</h2>
      <p>Privacy requests: support@quantforg.com</p>
    </LegalDoc>
  );
}
