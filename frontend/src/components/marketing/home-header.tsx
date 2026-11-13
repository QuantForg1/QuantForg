"use client";

import Link from "next/link";
import { useState } from "react";
import { Menu, X } from "lucide-react";
import { BrandLogo } from "@/components/brand/brand-logo";
import { useAuthOptional } from "@/providers/auth-provider";
import styles from "./home-landing.module.css";

const LINKS = [
  { href: "/", label: "Home" },
  { href: "/#features", label: "Features" },
  { href: "/#platform", label: "Platform" },
  { href: "/live", label: "Live Market" },
  { href: "/#how-it-works", label: "How It Works" },
  { href: "/#strategies", label: "Strategies" },
  { href: "/#security", label: "Security" },
  { href: "/pricing", label: "Pricing" },
] as const;

export function HomeHeader() {
  const [open, setOpen] = useState(false);
  const auth = useAuthOptional();
  const isAuthenticated = auth?.isAuthenticated ?? false;
  const loading = auth?.loading ?? false;
  const close = () => setOpen(false);

  return (
    <header className={styles.header}>
      <div className={styles.headerBar}>
        <Link href="/" className={styles.brandLink} onClick={close}>
          <BrandLogo size={36} priority caption={false} />
        </Link>
        <nav className={styles.desktopNav} aria-label="Homepage">
          {LINKS.map((item) => (
            <Link key={item.href} href={item.href}>
              {item.label}
            </Link>
          ))}
        </nav>
        <div className={styles.headerActions}>
          {!loading && isAuthenticated ? (
            <>
              <Link href="/dashboard" className={styles.buttonGhost}>
                Dashboard
              </Link>
              <Link href="/settings" className={styles.buttonPrimary}>
                Settings
              </Link>
            </>
          ) : (
            <>
              <Link href="/login" className={styles.buttonGhost}>
                Sign In
              </Link>
              <Link href="/register" className={styles.buttonPrimary}>
                Connect Your Broker
              </Link>
            </>
          )}
          <button
            type="button"
            className={styles.menuButton}
            aria-expanded={open}
            aria-controls="home-menu"
            onClick={() => setOpen((value) => !value)}
          >
            {open ? <X aria-hidden /> : <Menu aria-hidden />}
            <span className={styles.srOnly}>{open ? "Close menu" : "Open menu"}</span>
          </button>
        </div>
      </div>
      {open ? (
        <nav id="home-menu" className={styles.mobileNav} aria-label="Homepage mobile">
          {LINKS.map((item) => (
            <Link key={item.href} href={item.href} onClick={close}>
              {item.label}
            </Link>
          ))}
          {!loading && isAuthenticated ? (
            <Link href="/dashboard" onClick={close}>
              Dashboard
            </Link>
          ) : (
            <>
              <Link href="/login" onClick={close}>
                Sign In
              </Link>
              <Link href="/register" onClick={close}>
                Connect Your Broker
              </Link>
            </>
          )}
        </nav>
      ) : null}
    </header>
  );
}
