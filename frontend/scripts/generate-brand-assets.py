"""Generate QuantForg QF brand assets from official monogram sources."""

from __future__ import annotations

import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BRAND = PUBLIC / "brand"
ASSETS = Path(
    r"C:\Users\os\.cursor\projects\c-QuantForg-Workspace-QuantForg\assets"
)

SRC_A = ASSETS / "Teal_QF_Market_Trend_Logo-ea607afb-bef8-4510-86f3-bf74915e58a2.png"
SRC_B = (
    ASSETS
    / "ChatGPT_Image_Nov_8__2026__04_12_21_PM-93b2b855-7efa-4549-b95e-958d894e6059.png"
)

CHARCOAL = (17, 24, 39, 255)
WHITE = (255, 255, 255, 255)


def fit_square(im: Image.Image, size: int, bg=None, pad_ratio: float = 0.08) -> Image.Image:
    rgba = im.convert("RGBA")
    w, h = rgba.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), bg if bg else (0, 0, 0, 0))
    canvas.paste(rgba, ((side - w) // 2, (side - h) // 2), rgba)
    pad = int(side * pad_ratio)
    if pad > 0:
        inner = canvas.resize((side - 2 * pad, side - 2 * pad), Image.Resampling.LANCZOS)
        out = Image.new("RGBA", (side, side), bg if bg else (0, 0, 0, 0))
        out.paste(inner, (pad, pad), inner)
        canvas = out
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def save_png(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", optimize=True)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def knock_near_black(im: Image.Image, threshold: int = 14) -> Image.Image:
    out = im.copy()
    px = out.load()
    w, h = out.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if r < threshold and g < threshold and b < threshold:
                px[x, y] = (0, 0, 0, 0)
    return out


def make_horizontal(
    img: Image.Image,
    *,
    size_mark: int = 160,
    bg=CHARCOAL,
    fg=(245, 248, 255, 255),
    out_name: str = "quantforg-logo-horizontal.png",
) -> None:
    mark = fit_square(img, size_mark, bg=bg, pad_ratio=0.05)
    pad = 24
    text_w = int(size_mark * 3.2)
    canvas = Image.new("RGBA", (size_mark + pad + text_w, size_mark + pad * 2), bg)
    canvas.paste(mark, (pad, pad), mark)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", int(size_mark * 0.38))
        font_sm = ImageFont.truetype("arial.ttf", int(size_mark * 0.16))
    except OSError:
        font = ImageFont.load_default()
        font_sm = font
    tx = size_mark + pad + 12
    ty = pad + int(size_mark * 0.28)
    draw.text((tx, ty), "QuantForg", font=font, fill=fg)
    draw.text(
        (tx, ty + int(size_mark * 0.42)),
        "Trading Technology",
        font=font_sm,
        fill=(160, 176, 192, 255),
    )
    save_png(canvas, BRAND / out_name)


def main() -> None:
    src = SRC_A if SRC_A.stat().st_size >= SRC_B.stat().st_size else SRC_B
    alt = SRC_B if src == SRC_A else SRC_A
    img = Image.open(src).convert("RGBA")
    print(f"source {src.name} {img.size}")

    BRAND.mkdir(parents=True, exist_ok=True)
    archive = BRAND / "_archive_pre_qf"
    archive.mkdir(exist_ok=True)
    for name in ["quantforg-mark.png", "quantforg-mark-256.png"]:
        path = BRAND / name
        if path.exists() and not (archive / name).exists():
            shutil.copy2(path, archive / name)

    mark = fit_square(img, 1024, bg=CHARCOAL, pad_ratio=0.06)
    save_png(mark, BRAND / "quantforg-mark.png")
    mark256 = fit_square(img, 256, bg=CHARCOAL, pad_ratio=0.06)
    save_png(mark256, BRAND / "quantforg-mark-256.png")
    save_png(mark, BRAND / "quantforg-symbol.png")
    save_png(mark256, BRAND / "quantforg-symbol-256.png")
    save_png(fit_square(img, 192, bg=CHARCOAL, pad_ratio=0.04), BRAND / "quantforg-compact.png")
    save_png(fit_square(img, 512, bg=CHARCOAL, pad_ratio=0.06), BRAND / "quantforg-logo-dark.png")
    save_png(fit_square(img, 512, bg=WHITE, pad_ratio=0.06), BRAND / "quantforg-logo-light.png")

    mono = knock_near_black(fit_square(img, 512, bg=(0, 0, 0, 0), pad_ratio=0.06))
    px = mono.load()
    w, h = mono.size
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a == 0:
                continue
            lum = int(0.299 * r + 0.587 * g + 0.114 * b)
            v = min(255, int(lum * 1.05))
            px[x, y] = (v, v, v, a)
    save_png(mono, BRAND / "quantforg-logo-mono.png")

    make_horizontal(img, bg=CHARCOAL, out_name="quantforg-logo-horizontal.png")
    make_horizontal(
        img,
        bg=WHITE,
        fg=(17, 24, 39, 255),
        out_name="quantforg-logo-horizontal-light.png",
    )

    for size, name in [
        (16, "favicon-16x16.png"),
        (32, "favicon-32x32.png"),
        (180, "apple-touch-icon.png"),
        (192, "icon-192.png"),
        (512, "icon-512.png"),
    ]:
        icon = fit_square(img, size, bg=CHARCOAL, pad_ratio=0.08 if size >= 64 else 0.05)
        save_png(icon, PUBLIC / name)
        save_png(icon, BRAND / name)

    ico16 = fit_square(img, 16, bg=CHARCOAL, pad_ratio=0.05)
    ico16.save(
        PUBLIC / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    ico16.save(
        ROOT / "src" / "app" / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
    )
    print("wrote favicon.ico")

    og = Image.new("RGBA", (1200, 630), CHARCOAL)
    overlay = Image.new("RGBA", (1200, 630), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i, alpha in enumerate([40, 28, 16]):
        r = 380 - i * 60
        od.ellipse([900 - r, -r // 2, 900 + r, r], fill=(0, 212, 224, alpha))
    og = Image.alpha_composite(og, overlay)
    mark_og = knock_near_black(fit_square(img, 280, bg=(0, 0, 0, 0), pad_ratio=0.04))
    og.paste(mark_og, (80, (630 - 280) // 2), mark_og)
    draw = ImageDraw.Draw(og)
    try:
        f1 = ImageFont.truetype("arial.ttf", 64)
        f2 = ImageFont.truetype("arial.ttf", 28)
    except OSError:
        f1 = ImageFont.load_default()
        f2 = f1
    draw.text((420, 220), "QuantForg", font=f1, fill=(245, 248, 255, 255))
    draw.text((420, 310), "Trading technology platform", font=f2, fill=(0, 212, 224, 255))
    draw.text(
        (420, 360),
        "MT5 workflows · Risk controls · Subscription access",
        font=f2,
        fill=(160, 176, 192, 255),
    )
    save_png(og, PUBLIC / "og-image.png")
    save_png(og, BRAND / "og-image.png")

    shutil.copy2(src, BRAND / "quantforg-qf-source.png")
    shutil.copy2(alt, BRAND / "quantforg-qf-source-alt.png")
    print("DONE")


if __name__ == "__main__":
    main()
