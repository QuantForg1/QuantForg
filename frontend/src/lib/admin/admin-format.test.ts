import assert from "node:assert/strict";
import { brokerActions, statusActions, subscriptionTone, userStatusTone } from "./admin-format.ts";

assert.deepEqual(statusActions("active"), ["suspend", "deactivate"]);
assert.deepEqual(statusActions("suspended"), ["reactivate", "deactivate"]);
assert.deepEqual(statusActions("deactivated"), ["reactivate"]);
assert.deepEqual(brokerActions("active"), ["disable", "remove"]);
assert.deepEqual(brokerActions("disabled"), ["enable", "remove"]);
assert.deepEqual(brokerActions("revoked"), []);
assert.equal(userStatusTone("suspended"), "warning");
assert.equal(subscriptionTone("active"), "success");
assert.equal(subscriptionTone("expired"), "danger");
console.log("admin-format: ok");
