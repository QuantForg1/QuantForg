import assert from "node:assert/strict";
import { ADMIN_NAV_GROUPS, isAdminPath } from "@/components/admin/admin-nav-config";

const hrefs = ADMIN_NAV_GROUPS.flatMap((g) => g.items.map((i) => i.href));

assert.equal(isAdminPath("/admin/multi-account"), true);
assert.ok(
  hrefs.includes("/admin/multi-account"),
  "Admin nav must expose Multi-account ops",
);

console.log("multi-account-ops-nav.test.ts: ok");
