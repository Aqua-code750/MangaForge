from __future__ import annotations
from typing import List, Tuple, Dict, Any
from pydantic import BaseModel
from core.models import PanelScript, PanelSizeType, ProjectSettings


class Rect(BaseModel):
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def width(self) -> int:
        return max(0, self.x2 - self.x1)

    @property
    def height(self) -> int:
        return max(0, self.y2 - self.y1)

    def as_tuple(self) -> Tuple[int, int, int, int]:
        return (self.x1, self.y1, self.x2, self.y2)


def mm_to_px(mm: float, dpi: int = 300) -> int:
    """Convert millimeters to integer pixels at target DPI."""
    return int(round((mm / 25.4) * dpi))


def calculate_canvas_geometry(settings: ProjectSettings) -> Dict[str, Any]:
    """
    Computes canvas pixel dimensions including bleed, trim box, safe margin box,
    and printable live panel area.
    """
    dpi = settings.dpi
    # Total canvas with bleed on all 4 sides
    canvas_w_mm = settings.trim_width_mm + 2 * settings.bleed_mm
    canvas_h_mm = settings.trim_height_mm + 2 * settings.bleed_mm

    canvas_w = mm_to_px(canvas_w_mm, dpi)
    canvas_h = mm_to_px(canvas_h_mm, dpi)

    bleed_px = mm_to_px(settings.bleed_mm, dpi)
    safe_margin_px = mm_to_px(settings.safe_margin_mm, dpi)

    trim_rect = Rect(
        x1=bleed_px,
        y1=bleed_px,
        x2=canvas_w - bleed_px,
        y2=canvas_h - bleed_px,
    )

    safe_rect = Rect(
        x1=trim_rect.x1 + safe_margin_px,
        y1=trim_rect.y1 + safe_margin_px,
        x2=trim_rect.x2 - safe_margin_px,
        y2=trim_rect.y2 - safe_margin_px,
    )

    return {
        "canvas_width": canvas_w,
        "canvas_height": canvas_h,
        "bleed_px": bleed_px,
        "safe_margin_px": safe_margin_px,
        "trim_rect": trim_rect,
        "safe_rect": safe_rect,
    }


def calculate_page_layout(
    panels: List[PanelScript],
    live_area: Rect,
    gutter: int = 24,
    reading_direction: str = "RTL",
) -> List[Rect]:
    """
    Partition the live page area into bounding boxes for each panel.
    Honors:
      - Panel count and PanelSizeType (splash, wide, tall, small)
      - Standard Manga reading order: Top-to-Bottom, and Right-to-Left (RTL) or LTR
      - Gutter spacing between panels
    """
    n = len(panels)
    if n == 0:
        return []

    is_rtl = (reading_direction.upper() == "RTL")

    # 1 Panel: Full splash page
    if n == 1 or panels[0].panel_size == PanelSizeType.SPLASH:
        return [live_area]

    # 2 Panels
    if n == 2:
        # Check if side-by-side (tall) or stacked (wide/default)
        if panels[0].panel_size == PanelSizeType.TALL or panels[1].panel_size == PanelSizeType.TALL:
            half_w = (live_area.width - gutter) // 2
            left_rect = Rect(x1=live_area.x1, y1=live_area.y1, x2=live_area.x1 + half_w, y2=live_area.y2)
            right_rect = Rect(x1=live_area.x1 + half_w + gutter, y1=live_area.y1, x2=live_area.x2, y2=live_area.y2)
            return [right_rect, left_rect] if is_rtl else [left_rect, right_rect]
        else:
            half_h = (live_area.height - gutter) // 2
            top_rect = Rect(x1=live_area.x1, y1=live_area.y1, x2=live_area.x2, y2=live_area.y1 + half_h)
            bot_rect = Rect(x1=live_area.x1, y1=live_area.y1 + half_h + gutter, x2=live_area.x2, y2=live_area.y2)
            return [top_rect, bot_rect]

    # 3 Panels
    if n == 3:
        # Classic manga 3-tier: Top tier wide, Bottom tier split in two
        tier_h = (live_area.height - gutter) // 2
        top_rect = Rect(x1=live_area.x1, y1=live_area.y1, x2=live_area.x2, y2=live_area.y1 + tier_h)

        bot_y1 = live_area.y1 + tier_h + gutter
        half_w = (live_area.width - gutter) // 2
        b_left = Rect(x1=live_area.x1, y1=bot_y1, x2=live_area.x1 + half_w, y2=live_area.y2)
        b_right = Rect(x1=live_area.x1 + half_w + gutter, y1=bot_y1, x2=live_area.x2, y2=live_area.y2)

        if is_rtl:
            return [top_rect, b_right, b_left]
        else:
            return [top_rect, b_left, b_right]

    # 4 Panels: 2x2 Grid or 4 Tiers
    if n == 4:
        half_h = (live_area.height - gutter) // 2
        half_w = (live_area.width - gutter) // 2

        t_left = Rect(x1=live_area.x1, y1=live_area.y1, x2=live_area.x1 + half_w, y2=live_area.y1 + half_h)
        t_right = Rect(x1=live_area.x1 + half_w + gutter, y1=live_area.y1, x2=live_area.x2, y2=live_area.y1 + half_h)

        b_left = Rect(x1=live_area.x1, y1=live_area.y1 + half_h + gutter, x2=live_area.x1 + half_w, y2=live_area.y2)
        b_right = Rect(x1=live_area.x1 + half_w + gutter, y1=live_area.y1 + half_h + gutter, x2=live_area.x2, y2=live_area.y2)

        if is_rtl:
            return [t_right, t_left, b_right, b_left]
        else:
            return [t_left, t_right, b_left, b_right]

    # 5 Panels: Top tier (2 panels), Middle tier (1 wide panel), Bottom tier (2 panels)
    if n == 5:
        tier_h = (live_area.height - 2 * gutter) // 3
        half_w = (live_area.width - gutter) // 2

        # Tier 1 (top)
        y1_t1 = live_area.y1
        y2_t1 = y1_t1 + tier_h
        t1_l = Rect(x1=live_area.x1, y1=y1_t1, x2=live_area.x1 + half_w, y2=y2_t1)
        t1_r = Rect(x1=live_area.x1 + half_w + gutter, y1=y1_t1, x2=live_area.x2, y2=y2_t1)

        # Tier 2 (middle wide)
        y1_t2 = y2_t1 + gutter
        y2_t2 = y1_t2 + tier_h
        t2_wide = Rect(x1=live_area.x1, y1=y1_t2, x2=live_area.x2, y2=y2_t2)

        # Tier 3 (bottom)
        y1_t3 = y2_t2 + gutter
        y2_t3 = live_area.y2
        t3_l = Rect(x1=live_area.x1, y1=y1_t3, x2=live_area.x1 + half_w, y2=y2_t3)
        t3_r = Rect(x1=live_area.x1 + half_w + gutter, y1=y1_t3, x2=live_area.x2, y2=y2_t3)

        if is_rtl:
            return [t1_r, t1_l, t2_wide, t3_r, t3_l]
        else:
            return [t1_l, t1_r, t2_wide, t3_l, t3_r]

    # 6 or more panels: Even multi-tier division
    tier_count = (n + 1) // 2
    tier_h = (live_area.height - (tier_count - 1) * gutter) // tier_count
    half_w = (live_area.width - gutter) // 2

    rects: List[Rect] = []
    panel_idx = 0
    for t in range(tier_count):
        y1 = live_area.y1 + t * (tier_h + gutter)
        y2 = live_area.y2 if t == tier_count - 1 else y1 + tier_h

        remaining = n - panel_idx
        if remaining == 1:
            # Single panel on this tier
            rects.append(Rect(x1=live_area.x1, y1=y1, x2=live_area.x2, y2=y2))
            panel_idx += 1
        else:
            # Two panels on this tier
            r_left = Rect(x1=live_area.x1, y1=y1, x2=live_area.x1 + half_w, y2=y2)
            r_right = Rect(x1=live_area.x1 + half_w + gutter, y1=y1, x2=live_area.x2, y2=y2)
            if is_rtl:
                rects.extend([r_right, r_left])
            else:
                rects.extend([r_left, r_right])
            panel_idx += 2

    return rects

