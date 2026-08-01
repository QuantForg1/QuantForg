"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { EnterprisePlatform } from "@/components/ops/enterprise-platform";

export default function EnterpriseAdminPage() {
  return (
    <div>
      <PageHeader
        title="Enterprise Platform"
        description="Organizations, RBAC, API keys, audit, security, compliance, and executive reporting — additive SaaS controls. Never modifies trading, AI, OMS, MT5, COP, auth, or pricing."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/admin/noc">NOC</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/admin/customer-ops">Customer Ops</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/organizations">Organizations</Link>
            </Button>
          </div>
        }
      />
      <PageMotion>
        <EnterprisePlatform />
      </PageMotion>
    </div>
  );
}
