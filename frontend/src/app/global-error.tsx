"use client";

import { useEffect } from "react";

/** Root layout replacement for catastrophic render failures. Self-contained dark palette. */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    try {
      const payload = {
        kind: "route",
        message: error.message,
        digest: error.digest,
        route: typeof window !== "undefined" ? window.location.pathname : "/",
        build_version: process.env.NEXT_PUBLIC_BUILD_VERSION || "unknown",
        at: new Date().toISOString(),
      };
      const raw = localStorage.getItem("qf.ops.errors.v1");
      const prev = raw ? (JSON.parse(raw) as unknown[]) : [];
      localStorage.setItem(
        "qf.ops.errors.v1",
        JSON.stringify([{ id: `err_global_${Date.now()}`, ...payload }, ...prev].slice(0, 80)),
      );
    } catch {
      /* ignore */
    }
  }, [error]);

  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#061428",
          color: "#F5F8FF",
          fontFamily: "system-ui, sans-serif",
          padding: 24,
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: 440,
            border: "1px solid rgba(143, 184, 232, 0.18)",
            borderRadius: 14,
            background: "#0A2F59",
            padding: 24,
            boxShadow: "0 24px 64px rgba(2, 6, 23, 0.55)",
          }}
        >
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/brand/quantforg-mark-256.png"
            width={40}
            height={40}
            alt="QuantForg"
            style={{ display: "block", marginBottom: 16 }}
          />
          <h1 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 600 }}>
            Something went wrong
          </h1>
          <p style={{ margin: "0 0 16px", fontSize: 14, color: "#AFC4E2" }}>
            An unexpected error occurred. You can retry or return to the dashboard.
          </p>
          <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
            <button
              type="button"
              onClick={reset}
              style={{
                border: 0,
                borderRadius: 8,
                background: "linear-gradient(180deg, #3c9dff 0%, #0866ff 100%)",
                color: "#ffffff",
                padding: "8px 14px",
                fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Retry
            </button>
            <button
              type="button"
              onClick={() => {
                window.location.href = "/dashboard";
              }}
              style={{
                border: "1px solid rgba(143, 184, 232, 0.28)",
                borderRadius: 8,
                background: "#103B6B",
                color: "#F5F8FF",
                padding: "8px 14px",
                cursor: "pointer",
              }}
            >
              Dashboard
            </button>
          </div>
        </div>
      </body>
    </html>
  );
}
