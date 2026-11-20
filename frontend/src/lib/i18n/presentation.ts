/** Verified presentation helpers. They do not convert currencies or translate the product. */

export const VERIFIED_LOCALES = ["en-US"] as const;
export const VERIFIED_PAYMENT_METHODS = ["crypto"] as const;

export function localeSupport(requested: string | null | undefined): {
  locale: "en-US";
  supported: boolean;
  reason: "verified" | "language_not_verified";
} {
  const code = (requested ?? "").trim();
  if (code === "en-US" || code === "en") {
    return { locale: "en-US", supported: true, reason: "verified" };
  }
  return { locale: "en-US", supported: false, reason: "language_not_verified" };
}

export function formatMoney(amount: number, currency: string, locale = "en-US"): string {
  if (!Number.isFinite(amount) || !/^[A-Z]{3}$/.test(currency)) return "Unavailable";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    currencyDisplay: "code",
  }).format(amount);
}

export function formatNumber(amount: number, locale = "en-US"): string {
  if (!Number.isFinite(amount)) return "Unavailable";
  return new Intl.NumberFormat(locale, { maximumFractionDigits: 8 }).format(amount);
}

export function formatZonedDateTime(iso: string, timeZone: string, locale = "en-US"): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  try {
    return new Intl.DateTimeFormat(locale, {
      timeZone,
      dateStyle: "medium",
      timeStyle: "short",
    }).format(date);
  } catch {
    return "Unavailable";
  }
}

export function paymentMethodSupport(method: string): "verified" | "unsupported" {
  const name = method.trim().toLowerCase();
  return (VERIFIED_PAYMENT_METHODS as readonly string[]).includes(name)
    ? "verified"
    : "unsupported";
}
