"""Generate QuantForg QF brand assets from official monogram sources.

Sources of truth (supplied brand references):
  - Teal QF Finance Logo Icon (square app mark)
  - Teal QF Market Trend Logo (alternate / lockup source)

Background for opaque marks / PWA / favicons: Premium Blue Hybrid navy #061B35.
"""

from __future__ import annotations

import base64
import io
import shutil
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / "public"
BRAND = PUBLIC / "brand"
ASSETS = Path(
    r"C:\Users\os\.cursor\projects\c-QuantForg-Workspace-QuantForg\assets"
)

# Official supplied references (current filenames on disk).
SRC_ICON = ASSETS / "Teal_QF_Finance_Logo_Icon-7f5e3a38-ffac-4aa7-ac34-1bbf062d910d.png"
SRC_TREND = ASSETS / "Teal_QF_Market_Trend_Logo-30882642-d459-4442-9da4-c82a5b4f1aad.png"
SRC_MOUNTAIN = ASSETS / "Cinematic_Blue_Mountain_Sunrise-4774b2f6-75b9-44f0-856d-2364fc64ffa2.jpg"
SRC_TREND_ALT = ASSETS / "Teal_QF_Market_Trend_Logo-20e56062-f566-4baa-a2fd-23c821abbd83.png"
SRC_MOUNTAIN_ALT = ASSETS / "Cinematic_Blue_Mountain_Sunrise-e90adaa4-5339-4c21-931d-1a21678bc36c.jpg"
SRC_DASHBOARD = (
    ASSETS / "QuantForg_Gold_Trading_Overview-68f11af4-817d-42b5-8647-489e74e3f80c.jpg"
)

# Premium Blue Hybrid + logo-derived teal
NAVY = (6, 27, 53, 255)  # #061B35
PRIMARY_BLUE = (7, 86, 168, 255)  # #0756A8
ELECTRIC = (8, 124, 255, 255)  # #087CFF
TEAL = (0, 212, 224, 255)  # #00D4E0 (logo cyan glow)
WHITE = (255, 255, 255, 255)
FG = (245, 248, 255, 255)
MUTED = (160, 184, 208, 255)


def fit_square(
    im: Image.Image, size: int, bg=None, pad_ratio: float = 0.08
) -> Image.Image:
    rgba = im.convert("RGBA")
    w, h = rgba.size
    side = max(w, h)
    canvas = Image.new("RGBA", (side, side), bg if bg else (0, 0, 0, 0))
    canvas.paste(rgba, ((side - w) // 2, (side - h) // 2), rgba)
    pad = int(side * pad_ratio)
    if pad > 0:
        inner = canvas.resize(
            (side - 2 * pad, side - 2 * pad), Image.Resampling.LANCZOS
        )
        out = Image.new("RGBA", (side, side), bg if bg else (0, 0, 0, 0))
        out.paste(inner, (pad, pad), inner)
        canvas = out
    return canvas.resize((size, size), Image.Resampling.LANCZOS)


def save_png(im: Image.Image, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    im.save(path, format="PNG", optimize=True)
    print(f"wrote {path} ({path.stat().st_size} bytes)")


def knock_near_black(im: Image.Image, threshold: int = 18) -> Image.Image:
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
    bg=NAVY,
    fg=FG,
    muted=MUTED,
    out_name: str = "quantforg-logo-horizontal.png",
) -> None:
    mark = fit_square(img, size_mark, bg=bg, pad_ratio=0.05)
    pad = 24
    text_w = int(size_mark * 3.4)
    canvas = Image.new("RGBA", (size_mark + pad + text_w, size_mark + pad * 2), bg)
    canvas.paste(mark, (pad, pad), mark)
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("arial.ttf", int(size_mark * 0.38))
        font_sm = ImageFont.truetype("arial.ttf", int(size_mark * 0.15))
    except OSError:
        font = ImageFont.load_default()
        font_sm = font
    tx = size_mark + pad + 12
    ty = pad + int(size_mark * 0.26)
    draw.text((tx, ty), "QuantForg", font=font, fill=fg)
    draw.text(
        (tx, ty + int(size_mark * 0.42)),
        "Institutional AI Trading",
        font=font_sm,
        fill=muted,
    )
    save_png(canvas, BRAND / out_name)


def write_favicon_svg(mark_png: Image.Image, path: Path) -> None:
    """SVG favicon: navy tile + embedded transparent mark (scales cleanly)."""
    buf = io.BytesIO()
    mark_png.save(buf, format="PNG", optimize=True)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64" role="img" aria-label="QuantForg">
  <rect width="64" height="64" rx="12" fill="#061B35"/>
  <image href="data:image/png;base64,{b64}" x="6" y="6" width="52" height="52"/>
</svg>
"""
    path.write_text(svg, encoding="utf-8")
    print(f"wrote {path}")


def main() -> None:
    if not SRC_ICON.exists():
        raise SystemExit(f"Missing official icon source: {SRC_ICON}")
    if not SRC_TREND.exists() and SRC_TREND_ALT.exists():
        trend = SRC_TREND_ALT
    else:
        trend = SRC_TREND
    if not trend.exists():
        raise SystemExit(f"Missing official trend source: {SRC_TREND}")

    # Square app icon is primary mark; market-trend is secondary / transparent source.
    src = SRC_ICON if SRC_ICON.exists() else trend
    alt = trend
    img = Image.open(src).convert("RGBA")
    print(f"primary source {src.name} {img.size}")
    print(f"secondary source {alt.name}")

    BRAND.mkdir(parents=True, exist_ok=True)
    archive = BRAND / "_archive_pre_qf"
    archive.mkdir(exist_ok=True)
    for name in ["quantforg-mark.png", "quantforg-mark-256.png"]:
        path = BRAND / name
        if path.exists() and not (archive / name).exists():
            shutil.copy2(path, archive / name)

    # Opaque marks on Premium Blue Hybrid navy
    mark = fit_square(img, 1024, bg=NAVY, pad_ratio=0.06)
    save_png(mark, BRAND / "quantforg-mark.png")
    mark256 = fit_square(img, 256, bg=NAVY, pad_ratio=0.06)
    save_png(mark256, BRAND / "quantforg-mark-256.png")
    save_png(mark, BRAND / "quantforg-symbol.png")
    save_png(mark256, BRAND / "quantforg-symbol-256.png")
    save_png(
        fit_square(img, 192, bg=NAVY, pad_ratio=0.04), BRAND / "quantforg-compact.png"
    )
    save_png(
        fit_square(img, 512, bg=NAVY, pad_ratio=0.06), BRAND / "quantforg-logo-dark.png"
    )
    save_png(
        fit_square(img, 512, bg=WHITE, pad_ratio=0.06),
        BRAND / "quantforg-logo-light.png",
    )

    # Transparent marks for overlays (market-trend source knocks black tile)
    trend_img = Image.open(alt).convert("RGBA")
    transparent_src = trend_img if alt != src else img
    transparent_hi = knock_near_black(
        fit_square(transparent_src, 1024, bg=(0, 0, 0, 0), pad_ratio=0.04)
    )
    save_png(transparent_hi, BRAND / "quantforg-mark-transparent.png")
    transparent = knock_near_black(
        fit_square(transparent_src, 256, bg=(0, 0, 0, 0), pad_ratio=0.04)
    )
    save_png(transparent, BRAND / "quantforg-mark-transparent-256.png")
    save_png(
        knock_near_black(fit_square(transparent_src, 256, bg=(0, 0, 0, 0), pad_ratio=0.04)),
        BRAND / "quantforg-symbol-transparent-256.png",
    )
    save_png(
        knock_near_black(fit_square(transparent_src, 192, bg=(0, 0, 0, 0), pad_ratio=0.04)),
        BRAND / "quantforg-compact-transparent.png",
    )

    mono = transparent.copy()
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

    make_horizontal(img, bg=NAVY, out_name="quantforg-logo-horizontal.png")
    make_horizontal(
        img,
        bg=WHITE,
        fg=(6, 27, 53, 255),
        muted=(90, 110, 130, 255),
        out_name="quantforg-logo-horizontal-light.png",
    )

    # Favicon / PWA package
    favicon_sizes = [
        (16, "favicon-16x16.png"),
        (32, "favicon-32x32.png"),
        (48, "favicon-48x48.png"),
        (180, "apple-touch-icon.png"),
        (192, "icon-192.png"),
        (512, "icon-512.png"),
    ]
    for size, name in favicon_sizes:
        pad = 0.08 if size >= 64 else 0.05
        icon = fit_square(img, size, bg=NAVY, pad_ratio=pad)
        save_png(icon, PUBLIC / name)
        save_png(icon, BRAND / name)

    # Multi-size ICO
    ico_frames = [
        fit_square(img, s, bg=NAVY, pad_ratio=0.05) for s in (16, 32, 48)
    ]
    ico_frames[0].save(
        PUBLIC / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=ico_frames[1:],
    )
    ico_frames[0].save(
        ROOT / "src" / "app" / "favicon.ico",
        format="ICO",
        sizes=[(16, 16), (32, 32), (48, 48)],
        append_images=ico_frames[1:],
    )
    print("wrote favicon.ico")

    # SVG favicon (transparent mark on navy)
    write_favicon_svg(
        knock_near_black(fit_square(img, 52, bg=(0, 0, 0, 0), pad_ratio=0.02)),
        PUBLIC / "favicon.svg",
    )
    shutil.copy2(PUBLIC / "favicon.svg", BRAND / "favicon.svg")

    # Social OG image
    og = Image.new("RGBA", (1200, 630), NAVY)
    overlay = Image.new("RGBA", (1200, 630), (0, 0, 0, 0))
    od = ImageDraw.Draw(overlay)
    for i, (color, alpha) in enumerate(
        [
            ((8, 124, 255), 36),
            ((0, 212, 224), 28),
            ((7, 86, 168), 22),
        ]
    ):
        r = 420 - i * 70
        od.ellipse(
            [980 - r, -r // 2, 980 + r, r],
            fill=(color[0], color[1], color[2], alpha),
        )
    og = Image.alpha_composite(og, overlay)
    mark_og = knock_near_black(fit_square(img, 280, bg=(0, 0, 0, 0), pad_ratio=0.04))
    og.paste(mark_og, (72, (630 - 280) // 2), mark_og)
    draw = ImageDraw.Draw(og)
    try:
        f1 = ImageFont.truetype("arial.ttf", 64)
        f2 = ImageFont.truetype("arial.ttf", 26)
    except OSError:
        f1 = ImageFont.load_default()
        f2 = f1
    draw.text((400, 210), "QuantForg", font=f1, fill=FG)
    draw.text(
        (400, 295),
        "Institutional AI Trading Platform",
        font=f2,
        fill=TEAL,
    )
    draw.text(
        (400, 345),
        "MT5 · Market intelligence · Risk · Execution",
        font=f2,
        fill=MUTED,
    )
    save_png(og, PUBLIC / "og-image.png")
    save_png(og, BRAND / "og-image.png")

    # Cinematic mountain backdrop (marketing / auth atmosphere)
    mountain_path = SRC_MOUNTAIN if SRC_MOUNTAIN.exists() else SRC_MOUNTAIN_ALT
    if mountain_path.exists():
        mountain = Image.open(mountain_path).convert("RGB")
        mountain.save(BRAND / "mountain-backdrop.jpg", format="JPEG", quality=88, optimize=True)
        print(f"wrote {BRAND / 'mountain-backdrop.jpg'}")

    # Keep dashboard reference for design audits (not served as product UI chrome)
    if SRC_DASHBOARD.exists():
        shutil.copy2(SRC_DASHBOARD, BRAND / "_reference-overview.jpg")
        print(f"wrote {BRAND / '_reference-overview.jpg'}")

    shutil.copy2(src, BRAND / "quantforg-qf-source.png")
    shutil.copy2(alt, BRAND / "quantforg-qf-source-alt.png")
    print("DONE")


if __name__ == "__main__":
    main()
