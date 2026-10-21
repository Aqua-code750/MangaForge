import pytest
from pathlib import Path
from PIL import Image

from core.models import (
    ProjectSettings,
    ChapterScript,
    PageScript,
    PanelScript,
    PanelSizeType,
    DialogueItem,
    BubbleType,
)
from core.storage import StorageManager
from core.print_exporter import (
    pad_pages_to_multiple_of_four,
    export_print_volume,
)
from core.webtoon_exporter import (
    slice_webtoon_strip,
    build_webtoon_strip,
    export_webtoon_chapter,
    WARN_MAX_SLICES,
    WARN_MAX_MB,
)


def test_pad_pages_to_multiple_of_four():
    p1 = Image.new("RGB", (100, 100))

    # 1 page -> should pad to 4 (adds 3)
    padded, added = pad_pages_to_multiple_of_four([p1], (100, 100))
    assert len(padded) == 4
    assert added == 3

    # 4 pages -> should remain 4 (adds 0)
    padded, added = pad_pages_to_multiple_of_four([p1] * 4, (100, 100))
    assert len(padded) == 4
    assert added == 0

    # 6 pages -> should pad to 8 (adds 2)
    padded, added = pad_pages_to_multiple_of_four([p1] * 6, (100, 100))
    assert len(padded) == 8
    assert added == 2

    # 7 pages -> should pad to 8 (adds 1)
    padded, added = pad_pages_to_multiple_of_four([p1] * 7, (100, 100))
    assert len(padded) == 8
    assert added == 1


def test_webtoon_slicer_never_cuts_through_content():
    """
    Guarantees that slicing strictly occurs in the gaps between panels,
    and NEVER through any content interval.
    """
    total_w = 800
    total_h = 3200
    strip = Image.new("RGB", (total_w, total_h), color=(255, 255, 255))

    # 3 panels with gaps
    content_intervals = [
        (60, 600),     # Panel 1: y=60 to y=600
        # Gap: 600 to 720
        (720, 1250),   # Panel 2: y=720 to y=1250
        # Gap: 1250 to 1400
        (1400, 2100),  # Panel 3: y=1400 to y=2100
        # Gap: 2100 to 2200
        (2200, 2800),  # Panel 4: y=2200 to y=2800
    ]

    slices = slice_webtoon_strip(strip, content_intervals, max_slice_height=1280)

    # 1. Verify every slice height is <= 1280
    assert len(slices) >= 2
    for s in slices:
        assert s.height <= 1280
        assert s.width == 800

    # 2. Reconstruct cut points and verify none fall inside any content interval
    curr_y = 0
    cut_points = []
    for s in slices[:-1]:
        curr_y += s.height
        cut_points.append(curr_y)

    for cut in cut_points:
        for (start, end) in content_intervals:
            # Cut must NOT be strictly inside (start, end)
            assert not (start < cut < end), f"Cut point {cut} sliced through content interval ({start}, {end})!"


def test_print_and_webtoon_pipeline(tmp_path):
    storage = StorageManager(base_dir=tmp_path / "projects")
    settings = ProjectSettings(
        title="Spirit Blade",
        slug="spirit-blade",
        chapters_per_volume=1,
    )
    storage.init_project_structure(settings)

    script = ChapterScript(
        chapter_number=1,
        title="Opening Clash",
        summary="Battle begins",
        pages=[
            PageScript(
                page_number=1,
                page_notes="Page 1",
                panels=[
                    PanelScript(
                        panel_number=1,
                        panel_size=PanelSizeType.WIDE,
                        description="Clash",
                        dialogue=[DialogueItem(speaker="Ren", text="DON!", type=BubbleType.SFX)],
                    ),
                    PanelScript(
                        panel_number=2,
                        panel_size=PanelSizeType.SMALL,
                        description="Reaction",
                        dialogue=[DialogueItem(speaker="Ren", text="Take this!", type=BubbleType.SHOUT)],
                    ),
                ],
            )
        ],
    )
    storage.save_chapter_script(settings.slug, 1, script)

    # 1. Test Print Export
    print_res = export_print_volume(
        slug=settings.slug,
        storage=storage,
        settings=settings,
        pad_signature=True,
    )
    assert print_res["total_pages"] % 4 == 0
    assert print_res["pdf_path"].exists()
    assert print_res["pdf_path"].stat().st_size > 0

    # 2. Test Webtoon Export
    webtoon_res = export_webtoon_chapter(
        slug=settings.slug,
        chapter_number=1,
        script=script,
        storage=storage,
        settings=settings,
        img_format="PNG",
    )
    assert webtoon_res["slice_count"] >= 1
    assert webtoon_res["zip_path"].exists()
    assert webtoon_res["zip_path"].stat().st_size > 0
    assert isinstance(webtoon_res["warnings"], list)

