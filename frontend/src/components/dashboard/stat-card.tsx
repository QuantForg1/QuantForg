import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export function StatCard({
  label,
  value,
  hint,
  tone = "neutral",
}: {
  label: string;
  value: string;
  hint?: string;
  tone?: "neutral" | "up" | "down";
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm font-medium text-[var(--fg-muted)]">{label}</CardTitle>
      </CardHeader>
      <CardContent>
        <p
          className={cn(
            "tabular text-2xl font-semibold tracking-tight",
            tone === "up" && "text-[var(--success)]",
            tone === "down" && "text-[var(--danger)]",
          )}
        >
          {value}
        </p>
        {hint ? <p className="mt-1 text-xs text-[var(--fg-subtle)]">{hint}</p> : null}
      </CardContent>
    </Card>
  );
}
