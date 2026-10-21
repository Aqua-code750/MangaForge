import pytest
from PIL import Image
from core.models import (
    ProjectSettings,
    PageScript,
    PanelScript,
    DialogueItem,
    PanelSizeType,
    BubbleType,
)
from core.layout_engine import (
    Rect,
    mm_to_px,
    calculate_canvas_geometry,
    calculate_page_layout,
)
from core.bubble_renderer import (
    wrap_text_to_width,
    get_font,
    generate_starburst_polygon,
    render_bubble_overlay,
)
from core.page_composer import compose_single_page
from core.storage import StorageManager


def test_mm_to_px():
    # 25.4 mm at 300 DPI == 300 pixels
    assert mm_to_px(25.4, 300) == 300
    assert mm_to_px(128.0, 300) == 1512


def test_calculate_canvas_geometry():
    settings = ProjectSettings(
        title="Test Manga",
        slug="test-manga",
        trim_width_mm=128.0,
        trim_height_mm=182.0,
        bleed_mm=3.0,
        safe_margin_mm=10.0,
        dpi=300,
    )
    geom = calculate_canvas_geometry(settings)
    # Total canvas width = 128 + 6 = 134 mm -> approx 1583 px
    assert geom["canvas_width"] == mm_to_px(134.0, 300)
    assert geom["canvas_height"] == mm_to_px(188.0, 300)
    assert geom["trim_rect"].x1 == geom["bleed_px"]
    assert geom["safe_rect"].x1 == geom["trim_rect"].x1 + geom["safe_margin_px"]


def test_calculate_page_layout_rtl_vs_ltr():
    live_area = Rect(x1=100, y1=100, x2=1100, y2=1600)
    panels = [
        PanelScript(panel_number=1, panel_size=PanelSizeType.WIDE, description="Scene 1"),
        PanelScript(panel_number=2, panel_size=PanelSizeType.WIDE, description="Scene 2"),
        PanelScript(panel_number=3, panel_size=PanelSizeType.WIDE, description="Scene 3"),
    ]

    # Test RTL: In bottom tier, panel 2 is on the right, panel 3 is on the left
    rects_rtl = calculate_page_layout(panels, live_area, gutter=20, reading_direction="RTL")
    assert len(rects_rtl) == 3
    # Top tier
    assert rects_rtl[0].y1 == 100
    # Bottom tier panel 2 (right) vs panel 3 (left)
    assert rects_rtl[1].x1 > rects_rtl[2].x1

    # Test LTR: In bottom tier, panel 2 is on left, panel 3 is on right
    rects_ltr = calculate_page_layout(panels, live_area, gutter=20, reading_direction="LTR")
    assert len(rects_ltr) == 3
    assert rects_ltr[1].x1 < rects_ltr[2].x1


def test_layout_splash_page():
    live_area = Rect(x1=50, y1=50, x2=950, y2=1450)
    panels = [PanelScript(panel_number=1, panel_size=PanelSizeType.SPLASH, description="Hero splash")]
    rects = calculate_page_layout(panels, live_area)
    assert len(rects) == 1
    assert rects[0] == live_area


def test_starburst_polygon_generation():
    pts = generate_starburst_polygon(center_x=200, center_y=200, rx=50, ry=40, points_count=16)
    assert len(pts) == 16
    assert all(isinstance(p, tuple) and len(p) == 2 for p in pts)


def test_compose_single_page(tmp_path):
    storage = StorageManager(base_dir=tmp_path / "projects")
    settings = ProjectSettings(
        title="Test Manga",
        slug="test-manga",
        trim_width_mm=128.0,
        trim_height_mm=182.0,
        bleed_mm=3.0,
        safe_margin_mm=10.0,
        dpi=300,
    )
    storage.init_project_structure(settings)

    page_script = PageScript(
        page_number=1,
        page_notes="Opening clash",
        panels=[
            PanelScript(
                panel_number=1,
                panel_size=PanelSizeType.WIDE,
                description="Clash",
                dialogue=[
                    DialogueItem(speaker="Ren", text="I won't back down!", type=BubbleType.SHOUT),
                    DialogueItem(speaker="SFX", text="DON!!", type=BubbleType.SFX),
                ],
            ),
            PanelScript(
                panel_number=2,
                panel_size=PanelSizeType.SMALL,
                description="Reaction",
                dialogue=[
                    DialogueItem(speaker="Kazuma", text="Foolish child.", type=BubbleType.SPEECH),
                ],
            ),
        ],
    )

    # Compose page with safe margin guides
    img_with_guides = compose_single_page(
        slug=settings.slug,
        chapter_number=1,
        page_script=page_script,
        storage=storage,
        settings=settings,
        show_guides=True,
    )
    assert isinstance(img_with_guides, Image.Image)
    assert img_with_guides.size == (mm_to_px(134.0, 300), mm_to_px(188.0, 300))

    # Compose clean page without guides
    img_clean = compose_single_page(
        slug=settings.slug,
        chapter_number=1,
        page_script=page_script,
        storage=storage,
        settings=settings,
        show_guides=False,
    )
    assert img_clean.size == img_with_guides.size
