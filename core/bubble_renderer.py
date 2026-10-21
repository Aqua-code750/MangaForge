from __future__ import annotations
import math
import os
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from PIL import Image, ImageDraw, ImageFont

from core.models import BubbleType

FONTS_DIR = Path("assets/fonts")
COMIC_BOLD = FONTS_DIR / "comicbd.ttf"
COMIC_REG = FONTS_DIR / "comic.ttf"
IMPACT_FONT = FONTS_DIR / "impact.ttf"


def get_font(font_type: str = "bold", size: int = 24) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load bundled TrueType font with graceful fallback."""
    try:
        if font_type == "impact" and IMPACT_FONT.exists():
            return ImageFont.truetype(str(IMPACT_FONT), size)
        elif font_type == "regular" and COMIC_REG.exists():
            return ImageFont.truetype(str(COMIC_REG), size)
        elif COMIC_BOLD.exists():
            return ImageFont.truetype(str(COMIC_BOLD), size)
        elif COMIC_REG.exists():
            return ImageFont.truetype(str(COMIC_REG), size)
    except Exception:
        pass
    try:
        return ImageFont.load_default()
    except Exception:
        return ImageFont.load_default()


def wrap_text_to_width(
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    max_width: int,
    draw: ImageDraw.ImageDraw,
) -> List[str]:
    """Wraps text into lines that do not exceed max_width in pixels."""
    words = text.split()
    if not words:
        return []

    lines: List[str] = []
    current_line: List[str] = []

    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_w = bbox[2] - bbox[0]
        if line_w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                lines.append(word)
                current_line = []
    if current_line:
        lines.append(" ".join(current_line))

    return lines


def draw_speech_tail(
    draw: ImageDraw.ImageDraw,
    bubble_box: Tuple[int, int, int, int],
    tail_position: str = "bottom-center",
    fill: Tuple[int, int, int] = (255, 255, 255),
    outline: Tuple[int, int, int] = (15, 15, 15),
    stroke_width: int = 3,
) -> None:
    """Draw a triangle tail pointing away from the speech bubble."""
    x1, y1, x2, y2 = bubble_box
    cx = (x1 + x2) // 2
    cy = (y1 + y2) // 2
    w = x2 - x1
    h = y2 - y1

    tail_len = max(24, int(h * 0.45))
    tail_base = max(18, int(w * 0.22))

    pos = tail_position.lower()
    if "top" in pos:
        tip = (cx, y1 - tail_len)
        base1 = (cx - tail_base // 2, y1 + 3)
        base2 = (cx + tail_base // 2, y1 + 3)
    elif "left" in pos:
        tip = (x1 - tail_len, cy + 10)
        base1 = (x1 + 3, cy - tail_base // 2)
        base2 = (x1 + 3, cy + tail_base // 2)
    elif "right" in pos:
        tip = (x2 + tail_len, cy + 10)
        base1 = (x2 - 3, cy - tail_base // 2)
        base2 = (x2 - 3, cy + tail_base // 2)
    else:  # default bottom
        tip = (cx - 10, y2 + tail_len)
        base1 = (cx - tail_base, y2 - 3)
        base2 = (cx + tail_base // 2, y2 - 3)

    pts = [base1, tip, base2]
    draw.polygon(pts, fill=fill, outline=outline)


def draw_thought_trail(
    draw: ImageDraw.ImageDraw,
    bubble_box: Tuple[int, int, int, int],
    fill: Tuple[int, int, int] = (255, 255, 255),
    outline: Tuple[int, int, int] = (15, 15, 15),
    stroke_width: int = 3,
) -> None:
    """Draw 3 decreasing thought circles trailing from bottom of thought bubble."""
    x1, y1, x2, y2 = bubble_box
    cx = (x1 + x2) // 2
    cy = y2 + 10

    radii = [14, 9, 5]
    offsets_y = [14, 34, 50]
    offsets_x = [-10, -22, -30]

    for r, ox, oy in zip(radii, offsets_x, offsets_y):
        bx = cx + ox
        by = y2 + oy
        draw.ellipse([bx - r, by - r, bx + r, by + r], fill=fill, outline=outline, width=stroke_width)


def generate_starburst_polygon(
    center_x: int,
    center_y: int,
    rx: int,
    ry: int,
    points_count: int = 16,
    spike_factor: float = 0.28,
) -> List[Tuple[int, int]]:
    """Generate jagged spiky starburst polygon for shout bubbles."""
    pts = []
    step = 2 * math.pi / points_count
    for i in range(points_count):
        angle = i * step
        # Alternate between outer spike tip and inner trough
        r_mult = 1.0 + spike_factor if (i % 2 == 0) else 1.0 - spike_factor
        px = center_x + int(rx * r_mult * math.cos(angle))
        py = center_y + int(ry * r_mult * math.sin(angle))
        pts.append((px, py))
    return pts


def render_bubble_overlay(
    image: Image.Image,
    bubble_data: Dict[str, Any],
) -> None:
    """
    Renders a single dialogue or SFX bubble directly onto the image canvas.
    `bubble_data` attributes:
      - text: dialogue string
      - type: speech, thought, shout, whisper, sfx, narrator
      - center_x: pixel center X
      - center_y: pixel center Y
      - tail_position: bottom-center, top-left, etc.
      - font_size: target font size in px
    """
    draw = ImageDraw.Draw(image)
    text = bubble_data.get("text", "").strip()
    if not text:
        return

    b_type = bubble_data.get("type", "speech").lower()
    center_x = int(bubble_data.get("center_x", image.width // 2))
    center_y = int(bubble_data.get("center_y", image.height // 2))
    tail_pos = bubble_data.get("tail_position", "bottom-center")
    base_font_size = int(bubble_data.get("font_size", 28))

    # --- 1. SFX RENDERING ---
    if b_type == "sfx":
        sfx_font = get_font("impact", size=int(base_font_size * 1.8))
        # Draw bold SFX text with thick white/black outline
        outline_color = (0, 0, 0)
        fill_color = (255, 255, 255)
        outline_w = 4

        bbox = draw.textbbox((0, 0), text, font=sfx_font)
        tw = bbox[2] - bbox[0]
        th = bbox[3] - bbox[1]
        tx = center_x - tw // 2
        ty = center_y - th // 2

        # Draw drop shadow / outline
        for dx in range(-outline_w, outline_w + 1):
            for dy in range(-outline_w, outline_w + 1):
                if dx != 0 or dy != 0:
                    draw.text((tx + dx, ty + dy), text, fill=outline_color, font=sfx_font)
        draw.text((tx, ty), text, fill=fill_color, font=sfx_font)
        return

    # --- 2. NARRATOR BOX ---
    if b_type == "narrator":
        font = get_font("regular", size=base_font_size)
        max_line_w = int(image.width * 0.45)
        lines = wrap_text_to_width(text, font, max_line_w, draw)
        if not lines:
            return

        line_heights = [draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines]
        line_widths = [draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0] for line in lines]
        pad_x, pad_y = 16, 12
        box_w = max(line_widths) + pad_x * 2
        box_h = sum(line_heights) + (len(lines) - 1) * 8 + pad_y * 2

        x1 = center_x - box_w // 2
        y1 = center_y - box_h // 2
        x2 = x1 + box_w
        y2 = y1 + box_h

        draw.rectangle([x1, y1, x2, y2], fill=(245, 245, 240), outline=(15, 15, 15), width=3)
        curr_y = y1 + pad_y
        for line in lines:
            draw.text((x1 + pad_x, curr_y), line, fill=(15, 15, 15), font=font)
            curr_y += draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] + 8
        return

    # --- 3. SPEECH, SHOUT, THOUGHT, WHISPER BUBBLES ---
    font_kind = "bold" if b_type in ["speech", "shout"] else "regular"
    font = get_font(font_kind, size=base_font_size)

    # Estimate text width
    max_line_w = int(image.width * 0.35)
    lines = wrap_text_to_width(text, font, max_line_w, draw)
    if not lines:
        return

    line_heights = [draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1] for line in lines]
    line_widths = [draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0] for line in lines]
    max_w = max(line_widths) if line_widths else 80
    total_text_h = sum(line_heights) + (len(lines) - 1) * 6

    # Padding inside bubble
    pad_x = max(24, int(max_w * 0.28))
    pad_y = max(18, int(total_text_h * 0.32))

    bubble_w = max_w + pad_x * 2
    bubble_h = total_text_h + pad_y * 2

    x1 = center_x - bubble_w // 2
    y1 = center_y - bubble_h // 2
    x2 = x1 + bubble_w
    y2 = y1 + bubble_h
    bubble_box = (x1, y1, x2, y2)

    border_color = (15, 15, 15)
    fill_color = (255, 255, 255)
    border_width = 3 if b_type != "whisper" else 2

    # Draw Bubble Background & Perimeter
    if b_type == "shout":
        star_pts = generate_starburst_polygon(center_x, center_y, bubble_w // 2 + 10, bubble_h // 2 + 10, points_count=18)
        draw.polygon(star_pts, fill=fill_color, outline=border_color)
    elif b_type == "thought":
        draw.ellipse(bubble_box, fill=fill_color, outline=border_color, width=border_width)
        draw_thought_trail(draw, bubble_box, fill=fill_color, outline=border_color, stroke_width=border_width)
    else:  # speech or whisper
        draw.ellipse(bubble_box, fill=fill_color, outline=border_color, width=border_width)
        draw_speech_tail(draw, bubble_box, tail_position=tail_pos, fill=fill_color, outline=border_color, stroke_width=border_width)

    # Draw centered text lines
    curr_y = center_y - total_text_h // 2
    for line in lines:
        lw = draw.textbbox((0, 0), line, font=font)[2] - draw.textbbox((0, 0), line, font=font)[0]
        lh = draw.textbbox((0, 0), line, font=font)[3] - draw.textbbox((0, 0), line, font=font)[1]
        line_x = center_x - lw // 2
        draw.text((line_x, curr_y), line, fill=(15, 15, 15), font=font)
        curr_y += lh + 6

