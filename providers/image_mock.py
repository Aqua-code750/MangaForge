from __future__ import annotations
import io
from typing import Optional, List
from PIL import Image, ImageDraw, ImageFont

from providers.image_base import ImageProvider


class MockImageProvider(ImageProvider):
    """
    Mock Image Provider for offline development, tests, and previewing.
    Renders high-contrast manga panel placeholders with composition frames,
    camera angles, screentones, and metadata.
    """

    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: Optional[int] = None,
        reference_images: Optional[List[str]] = None,
    ) -> bytes:
        img = Image.new("RGB", (width, height), color=(250, 250, 250))
        draw = ImageDraw.Draw(img)

        # 1. Thick Outer Manga Panel Border
        border_width = 6
        margin = 14
        draw.rectangle(
            [margin, margin, width - margin, height - margin],
            outline=(15, 15, 15),
            width=border_width,
        )

        # 2. Rule of Thirds Guide Lines (subtle manga layout guides)
        third_x1, third_x2 = width // 3, (2 * width) // 3
        third_y1, third_y2 = height // 3, (2 * height) // 3
        draw.line([(third_x1, margin), (third_x1, height - margin)], fill=(230, 230, 230), width=1)
        draw.line([(third_x2, margin), (third_x2, height - margin)], fill=(230, 230, 230), width=1)
        draw.line([(margin, third_y1), (width - margin, third_y1)], fill=(230, 230, 230), width=1)
        draw.line([(margin, third_y2), (width - margin, third_y2)], fill=(230, 230, 230), width=1)

        # 3. Dynamic Manga Speedline / Screentone Accents in corners
        corner_depth = min(width, height) // 4
        for offset in range(margin + 8, corner_depth, 14):
            # Top-left corner
            draw.line([(margin, offset), (offset, margin)], fill=(210, 210, 210), width=1)
            # Bottom-right corner
            draw.line(
                [(width - margin, height - offset), (width - offset, height - margin)],
                fill=(210, 210, 210),
                width=1,
            )

        font = ImageFont.load_default()

        # 4. Top Header Banner
        banner_height = 34
        banner_top = margin + border_width
        draw.rectangle(
            [margin + border_width, banner_top, width - margin - border_width, banner_top + banner_height],
            fill=(15, 15, 15),
        )
        seed_label = f"Seed: {seed}" if seed is not None else "Seed: Auto"
        draw.text(
            (margin + 20, banner_top + 10),
            f"MANGAFORGE MOCK PANEL  |  {width}x{height}  |  {seed_label}",
            fill=(255, 255, 255),
            font=font,
        )

        # 5. Central Silhouette / Focal Box
        center_x, center_y = width // 2, height // 2
        focal_w, focal_h = min(width // 2, 280), min(height // 2, 280)
        draw.rectangle(
            [center_x - focal_w // 2, center_y - focal_h // 2, center_x + focal_w // 2, center_y + focal_h // 2],
            outline=(180, 180, 180),
            width=2,
        )
        draw.line([(center_x - 30, center_y), (center_x + 30, center_y)], fill=(150, 150, 150), width=2)
        draw.line([(center_x, center_y - 30), (center_x, center_y + 30)], fill=(150, 150, 150), width=2)

        # 6. Parse Camera Angle & Characters from prompt for display
        camera_str = "Shot Composition"
        chars_str = ""
        prompt_parts = prompt.split(", ")
        if len(prompt_parts) > 1:
            camera_str = prompt_parts[1].split(":")[0][:40]
        for part in prompt_parts:
            if part.startswith("Characters:"):
                chars_str = part[:60]
                break

        draw.text((center_x - focal_w // 2 + 10, center_y - 40), f"[ {camera_str.upper()} ]", fill=(60, 60, 60), font=font)
        if chars_str:
            draw.text((center_x - focal_w // 2 + 10, center_y - 15), chars_str, fill=(80, 80, 80), font=font)

        # 7. Bottom Prompt Box
        bottom_box_h = min(height // 3, 110)
        bottom_top = height - margin - border_width - bottom_box_h
        draw.rectangle(
            [margin + border_width, bottom_top, width - margin - border_width, height - margin - border_width],
            fill=(242, 242, 242),
            outline=(200, 200, 200),
            width=1,
        )

        # Wrap text lines
        words = prompt.split()
        lines: List[str] = []
        curr: List[str] = []
        max_chars = max(40, width // 14)
        for w in words:
            curr.append(w)
            if len(" ".join(curr)) > max_chars:
                lines.append(" ".join(curr))
                curr = []
        if curr:
            lines.append(" ".join(curr))

        draw.text((margin + 20, bottom_top + 8), "PROMPT PREVIEW (ENRICHED WITH LOCKED STYLE & CHARACTERS):", fill=(20, 20, 20), font=font)
        y_text = bottom_top + 28
        for line in lines[:4]:
            draw.text((margin + 20, y_text), line, fill=(70, 70, 70), font=font)
            y_text += 16

        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
