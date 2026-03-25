from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Best-effort font loader for macOS and fallback environments."""

    candidates = [
        "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        try:
            return ImageFont.truetype(path, size)
        except Exception:
            continue
    return ImageFont.load_default()


def build_placeholder(
    *,
    out_path: Path,
    width: int = 600,
    height: int = 900,
) -> None:
    """Generate a crisp, neutral fallback cover image.

    This is intentionally simple and brand-neutral, so it looks professional
    across all pages.
    """

    bg = (248, 250, 252)  # light neutral
    border = (203, 213, 225)
    text = (71, 85, 105)
    accent = (148, 163, 184)

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    pad = max(18, width // 25)
    draw.rounded_rectangle(
        [pad, pad, width - pad, height - pad],
        radius=28,
        outline=border,
        width=4,
    )
    draw.rounded_rectangle(
        [pad + 12, pad + 12, width - pad - 12, pad + 160],
        radius=22,
        outline=border,
        width=2,
    )

    font_title = _load_font(44)
    font_sub = _load_font(24)

    title = "Cover Unavailable"
    subtitle = "We'll fetch a real cover when possible."

    bbox = draw.textbbox((0, 0), title, font=font_title)
    tw = bbox[2] - bbox[0]
    draw.text(((width - tw) // 2, pad + 58), title, fill=text, font=font_title)

    bbox2 = draw.textbbox((0, 0), subtitle, font=font_sub)
    tw2 = bbox2[2] - bbox2[0]
    draw.text(
        ((width - tw2) // 2, pad + 118),
        subtitle,
        fill=accent,
        font=font_sub,
    )

    for y in range(pad + 210, height - pad - 60, 46):
        draw.line(
            [(pad + 60, y), (width - pad - 60, y)],
            fill=(226, 232, 240),
            width=3,
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_path, format="JPEG", quality=92, optimize=True, progressive=True)


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    out_path = project_root / "static" / "images" / "default_cover.jpg"
    build_placeholder(out_path=out_path)
    print(f"Wrote {out_path}")


if __name__ == "__main__":
    main()
