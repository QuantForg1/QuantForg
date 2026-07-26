const { loadEnvConfig } = require("@next/env");

const projectDir = process.cwd();
const { combinedEnv, loadedEnvFiles } = loadEnvConfig(projectDir, true);

const keys = [
  "NEXT_PUBLIC_API_BASE_URL",
  "NEXT_PUBLIC_MT5_GATEWAY_BASE_URL",
  "NEXT_PUBLIC_APP_URL",
  "NEXT_PUBLIC_APP_ENV",
  "NEXT_PUBLIC_MOCK_AI",
  "NEXT_PUBLIC_FF_AI",
  "NEXT_PUBLIC_FF_MT5",
  "NEXT_PUBLIC_FF_PAPER",
  "NEXT_PUBLIC_FF_WORKSPACE",
  "NEXT_PUBLIC_FF_BETA",
  "NEXT_PUBLIC_BETA_MODE",
  "NEXT_PUBLIC_MAINTENANCE_MODE",
  "NEXT_PUBLIC_READ_ONLY_MODE",
  "NEXT_PUBLIC_BUILD_VERSION",
  "NEXT_PUBLIC_ERROR_WEBHOOK_URL",
  "NEXT_PUBLIC_AUDIT_WEBHOOK_URL",
  "NEXT_PUBLIC_FEEDBACK_WEBHOOK_URL",
  "NEXT_PUBLIC_FEEDBACK_DISABLED",
];

const vars = {};
for (const k of keys) {
  const v = combinedEnv[k];
  if (v === undefined || v === "") {
    vars[k] = { present: false, value: null };
  } else if (/WEBHOOK|PASSWORD|SECRET|TOKEN/i.test(k)) {
    vars[k] = { present: true, value: "[set]" };
  } else {
    vars[k] = { present: true, value: v };
  }
}

const referencedInCode = {
  NEXT_PUBLIC_MT5_GATEWAY_BASE_URL: false,
  note: "No frontend source references NEXT_PUBLIC_MT5_GATEWAY_BASE_URL",
};

console.log(
  JSON.stringify(
    {
      loadedEnvFiles: loadedEnvFiles.map((f) => f.path),
      vars,
      referencedInCode,
    },
    null,
    2,
  ),
);
