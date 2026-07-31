import { ImageResponse } from "next/og";
import { readFile } from "node:fs/promises";
import { join } from "node:path";

export const size = { width: 32, height: 32 };
export const contentType = "image/png";

export default async function Icon() {
  const bytes = await readFile(join(process.cwd(), "public", "brand", "quantforg-mark.png"));
  const src = `data:image/png;base64,${Buffer.from(bytes).toString("base64")}`;

  return new ImageResponse(
    (
      <div
        style={{
          width: "100%",
          height: "100%",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "#0F1419",
          borderRadius: 6,
        }}
      >
        <img src={src} width={28} height={28} alt="" />
      </div>
    ),
    { ...size },
  );
}
