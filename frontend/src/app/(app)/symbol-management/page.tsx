"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { SymbolManagementWorkspace } from "@/components/ops/symbol-management-workspace";
import { Button } from "@/components/ui/button";

export default function SymbolManagementPage() {
  return (
    <div>
      <PageHeader
        title="Symbol Management"
        description="Owner/Admin trading universe — enable, disable, favorites, and scan priority. Selections persist and sync to ops allowlist for execution."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button asChild size="sm" variant="secondary">
              <Link href="/signals">Signal Center</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/broker">Broker</Link>
            </Button>
            <Button asChild size="sm" variant="outline">
              <Link href="/auto-trading">Auto Trading</Link>
            </Button>
          </div>
        }
      />
      <SymbolManagementWorkspace />
    </div>
  );
}
