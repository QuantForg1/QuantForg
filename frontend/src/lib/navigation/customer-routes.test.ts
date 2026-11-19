import assert from "node:assert/strict";
import { isCustomerRoute, isPrivilegedRole } from "./customer-routes.ts";

for (const ok of ["/dashboard", "/robot-control-center", "/symbols/XAUUSD", "/settings/", "/book?x=1", "/decision-evidence"]) {
  assert.ok(isCustomerRoute(ok), ok);
}
for (const retired of ["/history", "/history?x=1", "/risk-center", "/risk"]) {
  assert.equal(isCustomerRoute(retired), false, retired);
}
for (const no of ["/mission-control", "/admin", "/production-acceptance", "/dashboardx", "/ops/x", "/institutional-alpha"]) {
  assert.ok(!isCustomerRoute(no), no);
}
assert.ok(isPrivilegedRole("OWNER") && isPrivilegedRole("admin"));
assert.ok(!isPrivilegedRole("user") && !isPrivilegedRole(undefined));
console.log("customer routes ok");
