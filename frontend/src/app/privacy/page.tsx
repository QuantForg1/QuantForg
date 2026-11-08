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
        <li>Support messages and purchase or subscription requests you send to us.</li>
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
        authentication, and email delivery providers) may process data solely to run QuantForg.
        We do not publish another customer’s MT5 account, positions, balances, or credentials.
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
