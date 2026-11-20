export type TrustFigure = {
  value?: string | number | null;
  status?: string;
  method?: string;
  observed_at?: string | null;
  account_scope?: string;
  live_performance?: boolean;
};

/** Show a supplied figure. A missing value stays unavailable, never zero. */
export function figureLabel(figure: TrustFigure | undefined): string {
  if (!figure) return "Unavailable";
  const value = figure.value;
  if (value === null || value === undefined || value === "") {
    return statusLabel(figure.status);
  }
  return String(value);
}

export function statusLabel(status: string | undefined): string {
  const text = (status || "unavailable").trim();
  return text.length > 0 ? text.replaceAll("_", " ") : "unavailable";
}
