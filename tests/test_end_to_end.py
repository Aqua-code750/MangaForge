import pytest
from pathlib import Path

from core.models import (
    ProjectSettings,
    ProjectMode,
    Bible,
    VolumePlan,
    ChapterScript,
)
from core.storage import StorageManager
from core.pipeline import (
    generate_bible,
    generate_volume_plan,
    generate_chapter_script,
    generate_chapter_recap,
    build_panel_image_prompt,
    build_lettering_data_for_chapter,
)
from core.image_engine import (
    generate_panel_image,
    batch_generate_chapter_panels,
)
from core.page_composer import (
    compose_single_page,
    compose_and_save_page,
)
from core.print_exporter import export_print_volume
from core.webtoon_exporter import export_webtoon_chapter
from providers.text_mock import MockTextProvider
from providers.image_mock import MockImageProvider


def test_full_mangaforge_end_to_end_pipeline(tmp_path):
    """
    Complete end-to-end test verifying all 5 stages of the MangaForge pipeline:
      1. Project Initialization & Settings
      2. Story Bible Generation (with locked character visual descriptors)
      3. Volume Plan Generation (chapter breakdown)
      4. Chapter Scripting (pages, panels, dialogue, SFX) + Auto-Recap
      5. Panel Image Generation & SHA-256 Caching
      6. Page Composition with Lettering Overlays & Bleed
      7. Print Tankobon PDF Export with 4-page signature padding
      8. Webtoon 800px Vertical Strip Slicing & ZIP Packaging
    """
    storage = StorageManager(base_dir=tmp_path / "projects")
    text_provider = MockTextProvider()
    image_provider = MockImageProvider()

    # 1. Project Creation
    settings = ProjectSettings(
        title="Dragon of Kyoto",
        slug="dragon-of-kyoto",
        genre="Dark Fantasy Shonen",
        rating="Teen (13+)",
        mode=ProjectMode.BOTH,
        style_traits="High contrast black ink, dynamic screentones, sharp lineart",
        chapters_per_volume=5,
        trim_width_mm=128.0,
        trim_height_mm=182.0,
        bleed_mm=3.0,
        safe_margin_mm=10.0,
        dpi=300,
        reading_direction="RTL",
    )
    pdir = storage.init_project_structure(settings)
    assert pdir.exists()
    assert (pdir / "settings.json").exists()

    # 2. Stage 1: Generate Story Bible
    bible = generate_bible(settings, "A calligrapher controls living dragon ink in feudal Kyoto", text_provider)
    assert isinstance(bible, Bible)
    assert len(bible.characters) >= 2
    assert bible.characters[0].visual_descriptor != ""
    bible.is_approved = True
    storage.save_bible(settings.slug, bible)

    # 3. Stage 2: Generate Volume Plan
    volume_plan = generate_volume_plan(settings, bible, text_provider)
    assert isinstance(volume_plan, VolumePlan)
    assert len(volume_plan.chapters) == 5
    volume_plan.is_approved = True
    storage.save_volume_plan(settings.slug, volume_plan)

    # 4. Stage 3: Generate Chapter 1 Script
    script_ch1 = generate_chapter_script(
        settings=settings,
        bible=bible,
        volume_plan=volume_plan,
        chapter_number=1,
        provider=text_provider,
        previous_recaps={},
    )
    assert isinstance(script_ch1, ChapterScript)
    assert len(script_ch1.pages) >= 1
    script_ch1.is_approved = True
    storage.save_chapter_script(settings.slug, 1, script_ch1)

    # Auto-generate recap
    recap_ch1 = generate_chapter_recap(script_ch1, text_provider)
    storage.save_chapter_recap(settings.slug, 1, recap_ch1)
    recaps = storage.get_all_previous_recaps(settings.slug, 2)
    assert 1 in recaps

    # 5. Stage 4: Panel Artwork Generation & Caching
    batch_res = batch_generate_chapter_panels(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        script=script_ch1,
        bible=bible,
        settings=settings,
        provider=image_provider,
    )
    assert batch_res["completed"] == batch_res["total"]
    manifest = storage.load_panels_manifest(settings.slug, 1)
    assert len(manifest.panels) == batch_res["total"]

    # Test cache hit on repeat
    meta_p1, is_hit = generate_panel_image(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        page_number=1,
        panel=script_ch1.pages[0].panels[0],
        bible=bible,
        settings=settings,
        provider=image_provider,
        force_refresh=False,
    )
    assert is_hit is True  # Cached!

    # 6. Stage 5: Page Composition with Lettering
    for p in script_ch1.pages:
        saved_page_path = compose_and_save_page(
            slug=settings.slug,
            chapter_number=1,
            page_script=p,
            storage=storage,
            settings=settings,
            show_guides=False,
        )
        assert saved_page_path.exists()
        assert saved_page_path.stat().st_size > 0

    # 7. Stage 6A: Print Tankobon Export
    print_res = export_print_volume(
        slug=settings.slug,
        storage=storage,
        settings=settings,
        reverse_order=False,
        pad_signature=True,
    )
    assert print_res["total_pages"] % 4 == 0
    assert print_res["pdf_path"].exists()
    assert print_res["pdf_path"].stat().st_size > 0
    assert len(list(print_res["png_folder"].glob("*.png"))) == print_res["total_pages"]

    # 8. Stage 6B: Webtoon Export
    webtoon_res = export_webtoon_chapter(
        slug=settings.slug,
        chapter_number=1,
        script=script_ch1,
        storage=storage,
        settings=settings,
        img_format="PNG",
    )
    assert webtoon_res["slice_count"] >= 1
    assert webtoon_res["zip_path"].exists()
    assert webtoon_res["zip_path"].stat().st_size > 0
    assert webtoon_res["total_height_px"] >= 800
