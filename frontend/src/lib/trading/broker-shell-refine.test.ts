/**
 * Broker Accounts shell refinements — equal Broker/Server selectors, no standalone search field.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "../../");
const sidebar = readFileSync(join(root, "components/layout/sidebar.tsx"), "utf8");
const topbar = readFileSync(join(root, "components/layout/topbar.tsx"), "utf8");
const providers = readFileSync(join(root, "providers/app-providers.tsx"), "utf8");
const brokerLogo = readFileSync(join(root, "components/broker/broker-logo.tsx"), "utf8");
const broker = readFileSync(
  join(root, "components/broker/broker-config-workspace.tsx"),
  "utf8",
);

assert.match(sidebar, /BrandLogo/);
assert.match(sidebar, /href=\"\/dashboard\"/);
assert.equal(topbar.includes("BrandLogo"), false);
assert.equal(providers.includes("FirstRunChecklist"), false);
assert.match(providers, /ProductTour/);
assert.match(brokerLogo, /metatrader5-logo\.png/);
assert.doesNotMatch(broker, /AES-256-GCM/);
assert.match(broker, /broker_slug: selectedBroker\.slug/);
assert.match(broker, /function ServerSelect/);
assert.match(broker, /function BrokerSelect/);
assert.match(broker, /serverRowsForBroker/);
assert.match(broker, /useVirtualWindow/);
assert.doesNotMatch(broker, /Account type/);
assert.doesNotMatch(broker, /LIVE is primary/);
assert.equal(broker.includes("Search verified servers"), false);
assert.equal(broker.includes("RealLive"), false);
assert.match(broker, /weltradeApi\.connect/);
assert.match(broker, /clearPasswordField/);
assert.match(broker, /account_type: accountTypeResolved/);

console.log("broker-shell-refine: ok");
