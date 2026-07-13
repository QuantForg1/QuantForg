import { PageHeader } from "@/components/layout/page-header";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";

export default function SupportPage() {
  return (
    <div>
      <PageHeader
        title="Support"
        description="Operator help, status, and escalation paths."
      />
      <div className="grid gap-4 md:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Status</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-[var(--fg-muted)]">
            Check API health via the backend <code>/health</code> endpoint and Railway
            deployment status. Live trading remains gated by <code>EXECUTION_ENABLED</code>.
          </CardContent>
        </Card>
        <Card>
          <CardHeader>
            <CardTitle>Contact</CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-[var(--fg-muted)]">
            For production incidents, escalate through your QuantForg organization owners
            and include request IDs from API error responses.
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
