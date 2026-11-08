"use client";

import Link from "next/link";
import { PageHeader } from "@/components/layout/page-header";
import { PageMotion } from "@/components/desk/motion";
import { Button } from "@/components/ui/button";
import { AdminSupportCenter } from "@/components/admin/admin-support-center";

export default function AdminSupportPage() {
  return (
    <div className="min-w-0 space-y-4">
      <PageHeader
        eyebrow="Admin Portal"
        title="Support Management"
        description="Customer Operations support center — ticket status, assignment, and internal notes. Owner-verified session required."
        actions={
          <Button asChild size="sm" variant="outline">
            <Link href="/admin/customer-ops#support">COP support tab</Link>
          </Button>
        }
      />
      <PageMotion>
        <AdminSupportCenter />
      </PageMotion>
    </div>
  );
}
