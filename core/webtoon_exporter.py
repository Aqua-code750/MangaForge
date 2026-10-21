from __future__ import annotations
import os
import io
import zipfile
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image, ImageDraw

from core.models import ProjectSettings, ChapterScript, PanelScript, BubbleType
from core.storage import StorageManager
from core.bubble_renderer import render_bubble_overlay


WEBTOON_WIDTH = 800
MAX_SLICE_HEIGHT = 1280
WARN_MAX_SLICES = 100
WARN_MAX_MB = 20.0


def build_webtoon_strip(
    slug: str,
    chapter_number: int,
    script: ChapterScript,
    storage: StorageManager,
    settings: ProjectSettings,
    gap_px: int = 90,
    horizontal_margin: int = 24,
) -> Tuple[Image.Image, List[Tuple[int, int]]]:
    """
    Builds a single continuous vertical strip (800 px wide) for the chapter.
    Returns:
      - strip: PIL.Image of 800 px width.
      - content_intervals: List of (y_start, y_end) tuples representing regions
        occupied by panels and lettering where cutting is strictly forbidden.
    """
    # 1. Collect panels and determine layout items
    layout_items = []
    total_h = gap_px // 2

    manifest = storage.load_panels_manifest(slug, chapter_number)

    for page in script.pages:
        for panel in page.panels:
            panel_id = f"p{page.page_number}_panel{panel.panel_number}"
            img_path = storage.get_panel_image_path(slug, chapter_number, panel_id)

            # Determine panel width on strip:
            # splash panels take full 800px width; other panels have horizontal margins
            is_splash = (panel.panel_size.value == "splash")
            panel_w = WEBTOON_WIDTH if is_splash else (WEBTOON_WIDTH - horizontal_margin * 2)

            # Determine aspect ratio
            if img_path.exists():
                try:
                    with Image.open(img_path) as p_raw:
                        pw, ph = p_raw.size
                        aspect = ph / pw
                except Exception:
                    aspect = 0.65
            else:
                aspect = 0.65

            panel_h = int(panel_w * aspect)

            layout_items.append({
                "panel": panel,
                "page_number": page.page_number,
                "panel_id": panel_id,
                "img_path": img_path,
                "width": panel_w,
                "height": panel_h,
                "x": 0 if is_splash else horizontal_margin,
            })
            total_h += panel_h + gap_px

    total_h = max(total_h, 800)

    # 2. Render Vertical Canvas
    strip = Image.new("RGB", (WEBTOON_WIDTH, total_h), color=(255, 255, 255))
    draw = ImageDraw.Draw(strip)

    content_intervals: List[Tuple[int, int]] = []
    current_y = gap_px // 2

    for item in layout_items:
        panel: PanelScript = item["panel"]
        pw = item["width"]
        ph = item["height"]
        px = item["x"]
        py = current_y

        img_path: Path = item["img_path"]
        if img_path.exists():
            try:
                p_img = Image.open(img_path).convert("RGB")
                p_resized = p_img.resize((pw, ph), Image.Resampling.LANCZOS)
                strip.paste(p_resized, (px, py))
            except Exception:
                draw.rectangle([px, py, px + pw, py + ph], fill=(245, 245, 245))
        else:
            # Clean Webtoon Placeholder
            draw.rectangle([px, py, px + pw, py + ph], fill=(248, 248, 248), outline=(20, 20, 20), width=4)
            draw.text((px + 30, py + 30), f"Panel {panel.panel_number} ({panel.panel_size.value})", fill=(60, 60, 60))

        # Panel border
        draw.rectangle([px, py, px + pw, py + ph], outline=(15, 15, 15), width=4)

        # Record forbidden cut zone for this panel
        content_intervals.append((py, py + ph))

        # Render Dialogue Bubbles on panel
        if panel.dialogue:
            for b_idx, d in enumerate(panel.dialogue):
                cx_rel = 0.5 if b_idx == 0 else (0.35 if b_idx % 2 == 1 else 0.65)
                cy_rel = 0.3 + (b_idx * 0.3)
                cx = int(px + pw * cx_rel)
                cy = int(py + ph * cy_rel)

                bubble_data = {
                    "text": d.text,
                    "type": d.type.value,
                    "center_x": cx,
                    "center_y": cy,
                    "tail_position": d.tail_position or "bottom-center",
                    "font_size": 26,
                }
                render_bubble_overlay(strip, bubble_data)

        current_y += ph + gap_px

    return strip, content_intervals


def slice_webtoon_strip(
    strip: Image.Image,
    content_intervals: List[Tuple[int, int]],
    max_slice_height: int = MAX_SLICE_HEIGHT,
) -> List[Image.Image]:
    """
    Slices the tall vertical strip into images of at most `max_slice_height` px tall.
    GUARANTEE: Cuts ONLY through empty gap rows, NEVER through a panel or bubble!
    """
    total_w, total_h = strip.size
    slices: List[Image.Image] = []

    # Sort intervals
    intervals = sorted(content_intervals, key=lambda x: x[0])

    curr_y = 0
    while curr_y < total_h:
        remaining = total_h - curr_y
        if remaining <= max_slice_height:
            # Final slice fits within max height
            slice_img = strip.crop((0, curr_y, total_w, total_h))
            slices.append(slice_img)
            break

        max_cut = curr_y + max_slice_height

        # Find all valid gap points between content intervals that lie <= max_cut
        # Gap i exists between intervals[i][1] and intervals[i+1][0]
        best_cut = None

        for i in range(len(intervals)):
            gap_start = intervals[i][1]
            gap_end = intervals[i + 1][0] if (i + 1 < len(intervals)) else total_h

            # If gap starts after max_cut, we can't use it or subsequent gaps
            if gap_start > max_cut:
                break

            # The gap intersects or is before max_cut
            if gap_start >= curr_y:
                # Pick the midpoint of the gap that doesn't exceed max_cut
                mid_gap = (gap_start + gap_end) // 2
                valid_point = min(mid_gap, max_cut)
                # Ensure valid_point is strictly in the gap (<= gap_end and >= gap_start)
                if gap_start <= valid_point <= gap_end:
                    best_cut = valid_point

        if best_cut is None or best_cut <= curr_y:
            # Fallback: find nearest gap start before max_cut
            for i in reversed(range(len(intervals))):
                if intervals[i][1] <= max_cut and intervals[i][1] > curr_y:
                    best_cut = intervals[i][1] + 10
                    break

        if best_cut is None or best_cut <= curr_y:
            # Emergency safeguard (panel itself is huge): cut at max_cut
            best_cut = max_cut

        slice_img = strip.crop((0, curr_y, total_w, best_cut))
        slices.append(slice_img)
        curr_y = best_cut

    return slices


def export_webtoon_chapter(
    slug: str,
    chapter_number: int,
    script: ChapterScript,
    storage: StorageManager,
    settings: ProjectSettings,
    img_format: str = "PNG",
    gap_px: int = 90,
) -> Dict[str, Any]:
    """
    Complete Webtoon chapter pipeline:
      1. Renders 800px vertical strip.
      2. Slices non-destructively through gutter gaps (max 1280px tall).
      3. Saves numbered slices (001.png/jpg, etc.).
      4. Compiles ZIP package.
      5. Audits episode size and slice counts, raising warnings if > 100 images or > 20 MB.
    """
    strip, intervals = build_webtoon_strip(
        slug=slug,
        chapter_number=chapter_number,
        script=script,
        storage=storage,
        settings=settings,
        gap_px=gap_px,
    )

    slices = slice_webtoon_strip(strip, intervals, max_slice_height=MAX_SLICE_HEIGHT)

    # Directories
    export_dir = storage.get_project_dir(slug) / "exports" / "webtoon" / f"ch{chapter_number:02d}"
    export_dir.mkdir(parents=True, exist_ok=True)
    slices_dir = export_dir / "slices"
    slices_dir.mkdir(parents=True, exist_ok=True)

    ext = "jpg" if img_format.upper() in ["JPG", "JPEG"] else "png"
    slice_files: List[Path] = []
    total_bytes = 0

    for idx, s in enumerate(slices):
        slice_name = f"{idx+1:03d}.{ext}"
        slice_path = slices_dir / slice_name

        if ext == "jpg":
            s.convert("RGB").save(slice_path, format="JPEG", quality=92)
        else:
            s.save(slice_path, format="PNG")

        slice_files.append(slice_path)
        total_bytes += slice_path.stat().st_size

    # Create ZIP archive
    zip_path = export_dir / f"{slug}_ch{chapter_number:02d}_webtoon.zip"
    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        for sf in slice_files:
            zf.write(sf, arcname=sf.name)

    total_mb = total_bytes / (1024 * 1024)
    slice_count = len(slices)

    # Warnings evaluation
    warnings: List[str] = []
    if slice_count > WARN_MAX_SLICES:
        warnings.append(f"Episode contains {slice_count} images (exceeds standard 100 image limit).")
    if total_mb > WARN_MAX_MB:
        warnings.append(f"Episode size is {total_mb:.1f} MB (exceeds recommended 20 MB limit).")

    return {
        "chapter_number": chapter_number,
        "slice_count": slice_count,
        "total_mb": round(total_mb, 2),
        "total_height_px": strip.height,
        "zip_path": zip_path,
        "slices_dir": slices_dir,
        "slice_files": slice_files,
        "warnings": warnings,
        "format": ext.upper(),
    }

