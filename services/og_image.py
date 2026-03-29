import io
import math
import os
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# ─── Font Paths ──────────────────────────────────────────────────

ASSETS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets")
FONT_BOLD_PATH = os.path.join(ASSETS_DIR, "Roboto-Bold.ttf")
FONT_REGULAR_PATH = os.path.join(ASSETS_DIR, "Roboto-Regular.ttf")

# ─── Constants ───────────────────────────────────────────────────

WIDTH = 1200
HEIGHT = 630

TEMPLATES = {
    "blog": {
        "title_size": 64,
        "subtitle_size": 28,
        "meta_size": 22,
        "accent_bar": True,
        "accent_bar_height": 8,
        "layout": "left",
        "padding_x": 80,
        "padding_top": 100,
    },
    "minimal": {
        "title_size": 56,
        "subtitle_size": 26,
        "meta_size": 20,
        "accent_bar": False,
        "layout": "center",
        "padding_x": 120,
        "padding_top": 160,
    },
    "bold": {
        "title_size": 80,
        "subtitle_size": 32,
        "meta_size": 24,
        "accent_bar": True,
        "accent_bar_height": 12,
        "layout": "left",
        "padding_x": 80,
        "padding_top": 80,
    },
    "card": {
        "title_size": 52,
        "subtitle_size": 24,
        "meta_size": 20,
        "accent_bar": False,
        "layout": "center",
        "padding_x": 100,
        "padding_top": 140,
        "card_bg": True,
    },
}


# ─── Helpers ─────────────────────────────────────────────────────


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    """Convert hex color string to RGB tuple."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) == 3:
        hex_color = "".join(c * 2 for c in hex_color)
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def _lighten(rgb: tuple, factor: float = 0.3) -> tuple[int, int, int]:
    """Lighten a color by mixing with white."""
    return tuple(min(255, int(c + (255 - c) * factor)) for c in rgb)


def _darken(rgb: tuple, factor: float = 0.3) -> tuple[int, int, int]:
    """Darken a color by mixing toward black."""
    return tuple(max(0, int(c * (1 - factor))) for c in rgb)


def _with_alpha(rgb: tuple, alpha: int) -> tuple:
    """Add alpha channel to RGB tuple."""
    return (*rgb, alpha)


def _load_font(bold: bool, size: int) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD_PATH if bold else FONT_REGULAR_PATH
    try:
        return ImageFont.truetype(path, size=size)
    except IOError:
        return ImageFont.load_default()


def _wrap_text(
    text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.Draw
) -> list[str]:
    """Wrap text to fit within max_width pixels."""
    if draw.textlength(text, font=font) <= max_width:
        return [text]

    words = text.split(" ")
    lines = []
    current_line = ""

    for word in words:
        test_line = f"{current_line} {word}".strip()
        if draw.textlength(test_line, font=font) <= max_width:
            current_line = test_line
        else:
            if current_line:
                lines.append(current_line)
            current_line = word

    if current_line:
        lines.append(current_line)

    return lines


# ─── Background Renderers ────────────────────────────────────────


def _draw_solid(img: Image.Image, bg_rgb: tuple):
    """Solid color background."""
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg_rgb)


def _draw_gradient(img: Image.Image, bg_rgb: tuple, direction: str = "diagonal"):
    """Gradient background from bg_color to a lighter/darker variant."""
    color_start = bg_rgb
    color_end = _lighten(bg_rgb, 0.4)

    for y in range(HEIGHT):
        for x in range(WIDTH):
            if direction == "diagonal":
                t = (x / WIDTH + y / HEIGHT) / 2
            elif direction == "horizontal":
                t = x / WIDTH
            else:  # vertical
                t = y / HEIGHT

            r = int(color_start[0] + (color_end[0] - color_start[0]) * t)
            g = int(color_start[1] + (color_end[1] - color_start[1]) * t)
            b = int(color_start[2] + (color_end[2] - color_start[2]) * t)
            img.putpixel((x, y), (r, g, b))


def _draw_gradient_fast(img: Image.Image, bg_rgb: tuple, direction: str = "diagonal"):
    """Fast gradient using line-by-line drawing instead of pixel-by-pixel."""
    draw = ImageDraw.Draw(img)
    color_end = _lighten(bg_rgb, 0.4)

    if direction == "vertical" or direction == "diagonal":
        for y in range(HEIGHT):
            t = y / HEIGHT
            r = int(bg_rgb[0] + (color_end[0] - bg_rgb[0]) * t)
            g = int(bg_rgb[1] + (color_end[1] - bg_rgb[1]) * t)
            b = int(bg_rgb[2] + (color_end[2] - bg_rgb[2]) * t)
            draw.line([(0, y), (WIDTH, y)], fill=(r, g, b))
    else:  # horizontal
        for x in range(WIDTH):
            t = x / WIDTH
            r = int(bg_rgb[0] + (color_end[0] - bg_rgb[0]) * t)
            g = int(bg_rgb[1] + (color_end[1] - bg_rgb[1]) * t)
            b = int(bg_rgb[2] + (color_end[2] - bg_rgb[2]) * t)
            draw.line([(x, 0), (x, HEIGHT)], fill=(r, g, b))

    # For diagonal, add a subtle overlay shift
    if direction == "diagonal":
        overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        odraw = ImageDraw.Draw(overlay)
        for x in range(0, WIDTH, 2):
            t = x / WIDTH
            alpha = int(60 * t)
            odraw.line(
                [(x, 0), (x, HEIGHT)], fill=_with_alpha(color_end, alpha)
            )
        img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


def _draw_pattern(img: Image.Image, bg_rgb: tuple):
    """Geometric dot pattern background."""
    draw = ImageDraw.Draw(img)
    draw.rectangle([(0, 0), (WIDTH, HEIGHT)], fill=bg_rgb)

    dot_color = _lighten(bg_rgb, 0.12)
    spacing = 40
    radius = 3

    for y in range(0, HEIGHT, spacing):
        for x in range(0, WIDTH, spacing):
            draw.ellipse(
                [x - radius, y - radius, x + radius, y + radius],
                fill=dot_color,
            )


def _draw_mesh(img: Image.Image, bg_rgb: tuple):
    """Mesh gradient with overlapping radial blobs."""
    _draw_solid(img, bg_rgb)
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))

    blob_specs = [
        (200, 150, 300, _lighten(bg_rgb, 0.3), 50),
        (900, 100, 350, _lighten(bg_rgb, 0.25), 40),
        (500, 500, 280, _lighten(bg_rgb, 0.2), 35),
        (1100, 450, 250, _darken(bg_rgb, 0.1), 30),
    ]

    for bx, by, br, color, alpha in blob_specs:
        blob = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        bdraw = ImageDraw.Draw(blob)
        for r in range(br, 0, -4):
            a = int(alpha * (r / br))
            bdraw.ellipse(
                [bx - r, by - r, bx + r, by + r],
                fill=_with_alpha(color, a),
            )
        overlay = Image.alpha_composite(overlay, blob)

    # Apply blur for smooth mesh look
    overlay = overlay.filter(ImageFilter.GaussianBlur(radius=40))
    img.paste(Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB"))


BACKGROUND_RENDERERS = {
    "solid": _draw_solid,
    "gradient": lambda img, rgb: _draw_gradient_fast(img, rgb, "diagonal"),
    "gradient_horizontal": lambda img, rgb: _draw_gradient_fast(img, rgb, "horizontal"),
    "gradient_vertical": lambda img, rgb: _draw_gradient_fast(img, rgb, "vertical"),
    "pattern": _draw_pattern,
    "mesh": _draw_mesh,
}


# ─── Main Generator ──────────────────────────────────────────────


def generate_og_image(
    title: str,
    subtitle: str | None = None,
    bg_color: str = "#1a202c",
    text_color: str = "#ffffff",
    accent_color: str | None = None,
    template: str = "blog",
    background: str = "solid",
    author: str | None = None,
    tag: str | None = None,
    domain: str | None = None,
    reading_time: str | None = None,
) -> bytes:
    """
    Generate a 1200x630 Open Graph image with templates and styling.

    Templates: blog, minimal, bold, card
    Backgrounds: solid, gradient, gradient_horizontal, gradient_vertical, pattern, mesh
    """
    # Defaults
    bg_color = bg_color or "#1a202c"
    text_color = text_color or "#ffffff"
    template = template if template in TEMPLATES else "blog"
    background = background if background in BACKGROUND_RENDERERS else "solid"

    tmpl = TEMPLATES[template]
    bg_rgb = _hex_to_rgb(bg_color)
    text_rgb = _hex_to_rgb(text_color)
    accent_rgb = _hex_to_rgb(accent_color) if accent_color else _lighten(bg_rgb, 0.5)

    # Faded text color for secondary elements
    faded_rgb = (
        int(text_rgb[0] * 0.6 + bg_rgb[0] * 0.4),
        int(text_rgb[1] * 0.6 + bg_rgb[1] * 0.4),
        int(text_rgb[2] * 0.6 + bg_rgb[2] * 0.4),
    )

    # ─── Create image and draw background ────────────────────────
    img = Image.new("RGB", (WIDTH, HEIGHT), color=bg_rgb)
    BACKGROUND_RENDERERS[background](img, bg_rgb)
    draw = ImageDraw.Draw(img)

    # ─── Card background overlay ─────────────────────────────────
    if tmpl.get("card_bg"):
        card_overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
        card_draw = ImageDraw.Draw(card_overlay)
        card_margin = 60
        card_draw.rounded_rectangle(
            [card_margin, card_margin, WIDTH - card_margin, HEIGHT - card_margin],
            radius=24,
            fill=_with_alpha(bg_rgb, 200),
            outline=_with_alpha(accent_rgb, 80),
            width=2,
        )
        img = Image.alpha_composite(img.convert("RGBA"), card_overlay).convert("RGB")
        draw = ImageDraw.Draw(img)

    # ─── Load fonts ──────────────────────────────────────────────
    title_font = _load_font(bold=True, size=tmpl["title_size"])
    subtitle_font = _load_font(bold=False, size=tmpl["subtitle_size"])
    meta_font = _load_font(bold=False, size=tmpl["meta_size"])
    tag_font = _load_font(bold=True, size=tmpl["meta_size"])

    padding_x = tmpl["padding_x"]
    max_text_width = WIDTH - (padding_x * 2)
    current_y = tmpl["padding_top"]
    is_center = tmpl["layout"] == "center"

    # ─── Accent bar (top) ────────────────────────────────────────
    if tmpl.get("accent_bar"):
        bar_h = tmpl["accent_bar_height"]
        draw.rectangle([(0, 0), (WIDTH, bar_h)], fill=accent_rgb)
        current_y = max(current_y, bar_h + 40)

    # ─── Tag pill ────────────────────────────────────────────────
    if tag:
        tag_text = tag.upper()
        tag_bbox = draw.textbbox((0, 0), tag_text, font=tag_font)
        tag_w = tag_bbox[2] - tag_bbox[0] + 24
        tag_h = tag_bbox[3] - tag_bbox[1] + 14

        if is_center:
            tag_x = (WIDTH - tag_w) // 2
        else:
            tag_x = padding_x

        draw.rounded_rectangle(
            [tag_x, current_y, tag_x + tag_w, current_y + tag_h],
            radius=6,
            fill=accent_rgb,
        )
        # Tag text color: dark if accent is light, white if accent is dark
        tag_brightness = sum(accent_rgb) / 3
        tag_text_color = (0, 0, 0) if tag_brightness > 140 else (255, 255, 255)
        draw.text(
            (tag_x + 12, current_y + 5),
            tag_text,
            font=tag_font,
            fill=tag_text_color,
        )
        current_y += tag_h + 24

    # ─── Title ───────────────────────────────────────────────────
    title_lines = _wrap_text(title, title_font, max_text_width, draw)
    # Limit to 3 lines max
    if len(title_lines) > 3:
        title_lines = title_lines[:3]
        title_lines[2] = title_lines[2][:len(title_lines[2]) - 3] + "..."

    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=title_font)
        line_h = bbox[3] - bbox[1]

        if is_center:
            line_w = bbox[2] - bbox[0]
            x = (WIDTH - line_w) // 2
        else:
            x = padding_x

        draw.text((x, current_y), line, font=title_font, fill=text_rgb)
        current_y += line_h + 12

    # ─── Subtitle ────────────────────────────────────────────────
    if subtitle:
        current_y += 16
        sub_lines = _wrap_text(subtitle, subtitle_font, max_text_width, draw)
        if len(sub_lines) > 2:
            sub_lines = sub_lines[:2]

        for line in sub_lines:
            bbox = draw.textbbox((0, 0), line, font=subtitle_font)
            line_h = bbox[3] - bbox[1]

            if is_center:
                line_w = bbox[2] - bbox[0]
                x = (WIDTH - line_w) // 2
            else:
                x = padding_x

            draw.text((x, current_y), line, font=subtitle_font, fill=faded_rgb)
            current_y += line_h + 10

    # ─── Bottom meta line (author, domain, reading_time) ─────────
    meta_parts = []
    if author:
        meta_parts.append(author)
    if domain:
        meta_parts.append(domain)
    if reading_time:
        meta_parts.append(reading_time)

    if meta_parts:
        meta_text = "  ·  ".join(meta_parts)
        meta_bbox = draw.textbbox((0, 0), meta_text, font=meta_font)
        meta_h = meta_bbox[3] - meta_bbox[1]
        meta_y = HEIGHT - 60 - meta_h

        if is_center:
            meta_w = meta_bbox[2] - meta_bbox[0]
            meta_x = (WIDTH - meta_w) // 2
        else:
            meta_x = padding_x

        # Separator line above meta
        sep_y = meta_y - 20
        sep_color = _with_alpha(text_rgb, 40) if img.mode == "RGBA" else faded_rgb
        draw.line(
            [(meta_x, sep_y), (WIDTH - padding_x, sep_y)],
            fill=(*faded_rgb, 60) if img.mode == "RGBA" else _darken(faded_rgb, 0.3),
            width=1,
        )
        draw.text((meta_x, meta_y), meta_text, font=meta_font, fill=faded_rgb)

    # ─── Output ──────────────────────────────────────────────────
    if img.mode == "RGBA":
        img = img.convert("RGB")

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    buf.seek(0)

    return buf.getvalue()
