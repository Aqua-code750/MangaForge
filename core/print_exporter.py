from __future__ import annotations
import os
import io
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
from PIL import Image

from reportlab.pdfgen import canvas
from reportlab.lib.units import mm

from core.models import ProjectSettings
from core.storage import StorageManager
from core.layout_engine import calculate_canvas_geometry
from core.page_composer import compose_single_page


def pad_pages_to_multiple_of_four(
    pages: List[Image.Image],
    canvas_size: Tuple[int, int] = (1583, 2220),
) -> Tuple[List[Image.Image], int]:
    """
    Standard print publishing requirement: pad total pages to a multiple of 4
    with blank white pages for booklet signature folding.
    Returns (padded_pages, blank_pages_added).
    """
    count = len(pages)
    if count == 0:
        return [], 0

    remainder = count % 4
    if remainder == 0:
        return list(pages), 0

    needed = 4 - remainder
    padded = list(pages)
    for _ in range(needed):
        blank = Image.new("RGB", canvas_size, color=(255, 255, 255))
        padded.append(blank)

    return padded, needed


def create_pdf_from_images(
    images: List[Image.Image],
    output_pdf_path: Path,
    width_mm: float,
    height_mm: float,
) -> Path:
    """Compile PIL images into a high-resolution print PDF via ReportLab."""
    output_pdf_path.parent.mkdir(parents=True, exist_ok=True)

    # Convert millimeters to PostScript points (72 points per inch)
    page_w_pt = (width_mm / 25.4) * 72.0
    page_h_pt = (height_mm / 25.4) * 72.0

    pdf = canvas.Canvas(str(output_pdf_path), pagesize=(page_w_pt, page_h_pt))

    for idx, img in enumerate(images):
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        buf.seek(0)

        from reportlab.lib.utils import ImageReader
        reader = ImageReader(buf)
        pdf.drawImage(reader, 0, 0, width=page_w_pt, height=page_h_pt)
        pdf.showPage()

    pdf.save()
    return output_pdf_path


def export_print_volume(
    slug: str,
    storage: StorageManager,
    settings: ProjectSettings,
    reverse_order: bool = False,
    pad_signature: bool = True,
    chapter_filter: Optional[int] = None,
) -> Dict[str, Any]:
    """
    Assemble and export print-ready Tankobon volume:
      1. Collects and composes all pages across the volume (or selected chapter).
      2. Reverses page order if requested (for right-to-left binding handling).
      3. Pads total pages to a multiple of 4 with blank pages.
      4. Compiles print-ready PDF with bleed.
      5. Exports high-res numbered PNG folder.
    """
    geom = calculate_canvas_geometry(settings)
    canvas_w = geom["canvas_width"]
    canvas_h = geom["canvas_height"]
    canvas_w_mm = settings.trim_width_mm + 2 * settings.bleed_mm
    canvas_h_mm = settings.trim_height_mm + 2 * settings.bleed_mm

    collected_pages: List[Image.Image] = []
    page_labels: List[str] = []

    # Determine chapters to include
    if chapter_filter is not None:
        target_chapters = [chapter_filter]
    else:
        target_chapters = list(range(1, settings.chapters_per_volume + 1))

    for ch_num in target_chapters:
        script = storage.load_chapter_script(slug, ch_num)
        if not script:
            continue

        for page in script.pages:
            let_data = storage.load_page_lettering(slug, ch_num, page.page_number)
            page_img = compose_single_page(
                slug=slug,
                chapter_number=ch_num,
                page_script=page,
                storage=storage,
                settings=settings,
                lettering_data=let_data,
                show_guides=False,
            )
            collected_pages.append(page_img)
            page_labels.append(f"Ch{ch_num:02d}_Page{page.page_number:02d}")

    original_count = len(collected_pages)
    if original_count == 0:
        raise ValueError("No scripted pages found to export.")

    # Apply RTL reverse page order if requested (noted in README for RTL binding)
    if reverse_order:
        collected_pages.reverse()
        page_labels.reverse()

    # Pad to multiple of 4
    blank_added = 0
    if pad_signature:
        collected_pages, blank_added = pad_pages_to_multiple_of_four(
            collected_pages,
            canvas_size=(canvas_w, canvas_h),
        )
        for b_idx in range(blank_added):
            page_labels.append(f"Blank_Padding_{b_idx+1:02d}")

    # Output paths in projects/<slug>/exports/print/
    exports_dir = storage.get_project_dir(slug) / "exports" / "print"
    exports_dir.mkdir(parents=True, exist_ok=True)
    png_folder = exports_dir / "png_pages"
    png_folder.mkdir(parents=True, exist_ok=True)

    # Save individual numbered PNGs
    for idx, (img, label) in enumerate(zip(collected_pages, page_labels)):
        png_path = png_folder / f"page_{idx+1:03d}_{label}.png"
        img.save(png_path, format="PNG")

    # Generate print PDF
    suffix = f"ch{chapter_filter:02d}" if chapter_filter else "volume_01"
    pdf_filename = f"{slug}_{suffix}_print_ready.pdf"
    pdf_path = exports_dir / pdf_filename

    create_pdf_from_images(
        images=collected_pages,
        output_pdf_path=pdf_path,
        width_mm=canvas_w_mm,
        height_mm=canvas_h_mm,
    )

    return {
        "original_pages": original_count,
        "blank_added": blank_added,
        "total_pages": len(collected_pages),
        "pdf_path": pdf_path,
        "png_folder": png_folder,
        "canvas_size_px": (canvas_w, canvas_h),
        "canvas_size_mm": (canvas_w_mm, canvas_h_mm),
        "reverse_order": reverse_order,
    }

