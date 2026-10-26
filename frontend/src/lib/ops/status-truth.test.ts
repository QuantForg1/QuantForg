/**
 * Run: node --experimental-strip-types src/lib/ops/status-truth.test.ts
 */
import assert from "node:assert/strict";
import {
  adapterExecutionEnabled,
  adapterExecutionLabel,
  railwayProcessOk,
} from "./status-truth.ts";

assert.equal(adapterExecutionEnabled({}), null);
assert.equal(adapterExecutionLabel({}), "unknown");
assert.equal(adapterExecutionEnabled({ execution_enabled: false }), false);
assert.equal(adapterExecutionLabel({ execution_enabled: false }), "disabled");
assert.equal(
  adapterExecutionLabel({ configuration: { execution_enabled: true } }),
  "enabled",
);
assert.equal(
  adapterExecutionEnabled({
    execution_enabled: false,
    configuration: { execution_enabled: true },
  }),
  false,
);

const servicesUp = {
  services: [
    { name: "api", status: "up" },
    { name: "mt5_gateway", status: "down" },
  ],
};

assert.equal(
  railwayProcessOk({
    servicesHealth: servicesUp,
    servicesHealthSuccess: true,
    servicesHealthError: false,
    observability: { components: { api: { status: "down" } } },
    apiHealth: null,
    apiHealthError: true,
    apiHealthSuccess: false,
  }),
  true,
);

assert.equal(
  railwayProcessOk({
    servicesHealth: { services: [{ name: "api", status: "down" }] },
    servicesHealthSuccess: true,
    servicesHealthError: false,
    observability: { components: { api: { status: "healthy" } } },
    apiHealth: { status: "ok" },
    apiHealthError: false,
    apiHealthSuccess: true,
  }),
  false,
);

assert.equal(
  railwayProcessOk({
    servicesHealth: { as_of: "t", services: [{ name: "database", status: "up" }] },
    servicesHealthSuccess: true,
    servicesHealthError: false,
    observability: null,
    apiHealth: null,
    apiHealthError: true,
    apiHealthSuccess: false,
  }),
  true,
);

assert.equal(
  railwayProcessOk({
    servicesHealth: undefined,
    servicesHealthSuccess: false,
    servicesHealthError: false,
    observability: { components: { api: { status: "degraded" } } },
    apiHealth: { status: "ok" },
    apiHealthError: false,
    apiHealthSuccess: true,
  }),
  true,
);

assert.equal(
  railwayProcessOk({
    servicesHealth: { railway: { status: "down" } },
    servicesHealthSuccess: false,
    servicesHealthError: true,
    observability: {},
    apiHealth: null,
    apiHealthError: true,
    apiHealthSuccess: false,
  }),
  false,
);

assert.equal(
  railwayProcessOk({
    servicesHealth: undefined,
    servicesHealthSuccess: false,
    servicesHealthError: true,
    observability: {},
    apiHealth: null,
    apiHealthError: true,
    apiHealthSuccess: false,
  }),
  false,
);

assert.equal(
  railwayProcessOk({
    servicesHealth: undefined,
    servicesHealthSuccess: false,
    servicesHealthError: false,
    observability: undefined,
    apiHealth: undefined,
    apiHealthError: false,
    apiHealthSuccess: false,
  }),
  null,
);

console.log("status-truth tests passed");
