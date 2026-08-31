/**
 * Phase 73 — trader rail never exposes Admin; live-trading lives under /admin.
 */
import assert from "node:assert/strict";
import {
  TRADER_DESK_ORDER,
  visiblePrimaryRail,
  isOpsNavHref,
} from "../../components/layout/nav-config.ts";

const traderRail = visiblePrimaryRail(true);
assert.ok(traderRail.every((item) => item.href !== "/admin"));
assert.ok(traderRail.every((item) => item.href !== "/admin/live-trading"));
assert.ok(isOpsNavHref("/admin/live-trading"));
for (const href of TRADER_DESK_ORDER) {
  assert.ok(
    traderRail.some((item) => item.href === href),
    `missing trader desk ${href}`,
  );
}
console.log("phase73-live-trading-nav: ok");
