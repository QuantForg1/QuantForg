/**
 * Phase 70 — trader rail never exposes Admin.
 */
import assert from "node:assert/strict";
import {
  TRADER_DESK_ORDER,
  visibleCommandItems,
  visiblePrimaryRail,
} from "../../components/layout/nav-config.ts";

const traderRail = visiblePrimaryRail(true);
assert.ok(traderRail.every((item) => item.href !== "/admin"));
assert.ok(
  traderRail.every((item) => !String(item.label).toLowerCase().includes("admin")),
);
for (const href of TRADER_DESK_ORDER) {
  assert.ok(
    traderRail.some((item) => item.href === href),
    `missing trader desk ${href}`,
  );
}

const filtered = visibleCommandItems(true, [
  {
    href: "/signals",
    label: "Signals",
    icon: traderRail[0]!.icon,
    hint: "",
    match: ["/signals"],
  },
  {
    href: "/admin",
    label: "Admin",
    icon: traderRail[0]!.icon,
    hint: "",
    match: ["/admin"],
  },
  {
    href: "/ops",
    label: "Ops",
    icon: traderRail[0]!.icon,
    hint: "",
    match: ["/ops"],
  },
]);
assert.ok(filtered.every((item) => item.href !== "/admin"));
assert.ok(filtered.every((item) => item.href !== "/ops"));
assert.equal(filtered.length, 1);

console.log("phase70-nav: ok");
