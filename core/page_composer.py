from __future__ import annotations
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any, List
from PIL import Image, ImageDraw, ImageFont

from core.models import (
    ProjectSettings,
    PageScript,
    PanelScript,
    ChapterScript,
    DialogueItem,
)
from core.storage import StorageManager
from core.layout_engine import (
    Rect,
    calculate_canvas_geometry,
    calculate_page_layout,
)
from core.bubble_renderer import render_bubble_overlay


def compose_single_page(
    slug: str,
    chapter_number: int,
    page_script: PageScript,
    storage: StorageManager,
    settings: ProjectSettings,
    lettering_data: Optional[Dict[str, Any]] = None,
    show_guides: bool = False,
    gutter_px: int = 24,
) -> Image.Image:
    """
    Composes a complete print-ready manga page:
      1. Initializes full canvas with 3mm bleed at 300 DPI.
      2. Computes panel grid bounding boxes via LayoutEngine (RTL or LTR).
      3. Pastes panel artwork fitted to bounding boxes with 4px black borders.
      4. Renders editable dialogue, thought, shout, whisper, and SFX bubbles.
      5. Optionally draws trim and safe-margin overlay guides.
    """
    geometry = calculate_canvas_geometry(settings)
    canvas_w = geometry["canvas_width"]
    canvas_h = geometry["canvas_height"]
    trim_rect: Rect = geometry["trim_rect"]
    safe_rect: Rect = geometry["safe_rect"]

    # 1. Base Canvas
    page_img = Image.new("RGB", (canvas_w, canvas_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(page_img)

    # 2. Compute panel bounding boxes within the live area (inside trim or safe margin)
    live_area = Rect(
        x1=safe_rect.x1,
        y1=safe_rect.y1,
        x2=safe_rect.x2,
        y2=safe_rect.y2,
    )
    panel_rects = calculate_page_layout(
        panels=page_script.panels,
        live_area=live_area,
        gutter=gutter_px,
        reading_direction=settings.reading_direction,
    )

    # 3. Paste Panel Artwork
    manifest = storage.load_panels_manifest(slug, chapter_number)

    for idx, panel in enumerate(page_script.panels):
        if idx >= len(panel_rects):
            break
        rect = panel_rects[idx]
        panel_id = f"p{page_script.page_number}_panel{panel.panel_number}"
        img_path = storage.get_panel_image_path(slug, chapter_number, panel_id)

        target_w = rect.width
        target_h = rect.height

        if img_path.exists():
            try:
                panel_raw = Image.open(img_path).convert("RGB")
                # Resize and crop to fill rect perfectly
                panel_fitted = panel_raw.resize((target_w, target_h), Image.Resampling.LANCZOS)
                page_img.paste(panel_fitted, (rect.x1, rect.y1))
            except Exception:
                draw.rectangle(rect.as_tuple(), fill=(245, 245, 245))
        else:
            # Placeholder for unrendered panel
            draw.rectangle(rect.as_tuple(), fill=(248, 248, 248))
            draw.text(
                (rect.x1 + 20, rect.y1 + 20),
                f"Panel {panel.panel_number} ({panel.panel_size.value.upper()})",
                fill=(100, 100, 100),
            )

        # Draw crisp manga panel border
        draw.rectangle(rect.as_tuple(), outline=(15, 15, 15), width=4)

    # 4. Render Lettering & Speech Bubbles Overlay
    if lettering_data and "bubbles" in lettering_data:
        bubbles = lettering_data["bubbles"]
    else:
        # Generate initial default bubble placements from page_script
        bubbles = []
        for idx, panel in enumerate(page_script.panels):
            p_rect = panel_rects[idx] if idx < len(panel_rects) else live_area
            for b_idx, d in enumerate(panel.dialogue):
                # Calculate default anchor
                cx_rel = 0.5 if b_idx == 0 else (0.35 if b_idx % 2 == 1 else 0.65)
                cy_rel = 0.28 + (b_idx * 0.26)
                cx = int(p_rect.x1 + p_rect.width * cx_rel)
                cy = int(p_rect.y1 + p_rect.height * cy_rel)

                bubbles.append({
                    "bubble_id": f"p{page_script.page_number}_panel{panel.panel_number}_b{b_idx+1}",
                    "panel_number": panel.panel_number,
                    "speaker": d.speaker,
                    "text": d.text,
                    "type": d.type.value,
                    "tail_position": d.tail_position or "bottom-center",
                    "center_x": cx,
                    "center_y": cy,
                    "font_size": 26,
                })

    for b in bubbles:
        render_bubble_overlay(page_img, b)

    # 5. Optional Safe Margin & Bleed Guides Overlay
    if show_guides:
        # Red / Magenta Bleed border (outer canvas boundary)
        draw.rectangle([2, 2, canvas_w - 3, canvas_h - 3], outline=(239, 68, 68), width=3)
        # Black Trim box (where the paper is cut)
        draw.rectangle(trim_rect.as_tuple(), outline=(30, 41, 59), width=2)
        # Cyan Safe Margin box (keep text inside this margin)
        draw.rectangle(safe_rect.as_tuple(), outline=(6, 182, 212), width=2)

        font = ImageFont.load_default()
        draw.text((10, 8), f"BLEED ({settings.bleed_mm}mm)", fill=(239, 68, 68), font=font)
        draw.text((trim_rect.x1 + 10, trim_rect.y1 + 8), "TRIM LINE", fill=(30, 41, 59), font=font)
        draw.text((safe_rect.x1 + 10, safe_rect.y1 + 8), f"SAFE MARGIN ({settings.safe_margin_mm}mm)", fill=(6, 182, 212), font=font)

    return page_img


def compose_and_save_page(
    slug: str,
    chapter_number: int,
    page_script: PageScript,
    storage: StorageManager,
    settings: ProjectSettings,
    lettering_data: Optional[Dict[str, Any]] = None,
    show_guides: bool = False,
) -> Path:
    """Compose single page and save to chapters/chXX/pages/page_XX.png."""
    page_img = compose_single_page(
        slug=slug,
        chapter_number=chapter_number,
        page_script=page_script,
        storage=storage,
        settings=settings,
        lettering_data=lettering_data,
        show_guides=show_guides,
    )
    pages_dir = storage.get_chapter_dir(slug, chapter_number) / "pages"
    pages_dir.mkdir(parents=True, exist_ok=True)
    out_path = pages_dir / f"page_{page_script.page_number:02d}.png"
    page_img.save(out_path, format="PNG")
    return out_path

