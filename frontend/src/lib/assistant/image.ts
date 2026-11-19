/** Read a user image and downscale it for the assistant (browser only). */
export const ASSISTANT_MAX_IMAGES = 3;
export const ASSISTANT_ACCEPTED = ["image/png", "image/jpeg", "image/webp", "image/gif"];
const MAX_EDGE = 1600;
const MAX_INPUT_BYTES = 15 * 1024 * 1024;

export async function prepareChartImage(file: File): Promise<string> {
  if (!ASSISTANT_ACCEPTED.includes(file.type)) {
    throw new Error("Attach a PNG, JPEG, WebP or GIF image.");
  }
  if (file.size > MAX_INPUT_BYTES) throw new Error("That image is too large (max 15 MB).");
  const original = await new Promise<string>((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result));
    reader.onerror = () => reject(new Error("The image could not be read."));
    reader.readAsDataURL(file);
  });
  const img = await new Promise<HTMLImageElement>((resolve, reject) => {
    const el = new Image();
    el.onload = () => resolve(el);
    el.onerror = () => reject(new Error("The image could not be opened."));
    el.src = original;
  });
  const scale = Math.min(1, MAX_EDGE / Math.max(img.width, img.height));
  if (scale === 1 && file.size <= 3 * 1024 * 1024) return original;
  const canvas = document.createElement("canvas");
  canvas.width = Math.max(1, Math.round(img.width * scale));
  canvas.height = Math.max(1, Math.round(img.height * scale));
  const ctx = canvas.getContext("2d");
  if (!ctx) return original;
  ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
  return canvas.toDataURL("image/jpeg", 0.88);
}
