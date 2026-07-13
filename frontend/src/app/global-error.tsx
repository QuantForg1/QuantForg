"use client";

import { useEffect } from "react";

/** Root layout replacement for catastrophic render failures. */
export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("global_error", {
      message: error.message,
      digest: error.digest,
    });
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
          background: "#0b1016",
          color: "#e8eef7",
          fontFamily: "system-ui, sans-serif",
          padding: 24,
        }}
      >
        <div
          style={{
            width: "100%",
            maxWidth: 440,
            border: "1px solid #2a3a4f",
            borderRadius: 12,
            background: "#141c27",
            padding: 24,
          }}
        >
          <h1 style={{ margin: "0 0 8px", fontSize: 18 }}>Something went wrong</h1>
          <p style={{ margin: "0 0 16px", fontSize: 14, color: "#9aabc2" }}>
            An unexpected error occurred. You can retry or return to the dashboard.
          </p>
          <div style={{ display: "flex", gap: 8 }}>
            <button
              type="button"
              onClick={reset}
              style={{
                border: 0,
                borderRadius: 8,
                background: "#2dd4bf",
                color: "#042f2e",
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
                border: "1px solid #2a3a4f",
                borderRadius: 8,
                background: "#1a2433",
                color: "#e8eef7",
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
