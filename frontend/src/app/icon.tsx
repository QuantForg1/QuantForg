import { ImageResponse } from "next/og";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#2dd4bf",
          color: "#042f2e",
          fontSize: 20,
          fontWeight: 700,
        }}
      >
        Q
      </div>
    ),
    { ...size },
  );
}
