import io
import pytest
from PIL import Image
from core.models import (
    ProjectSettings,
    Bible,
    CharacterSheet,
    ChapterScript,
    PageScript,
    PanelScript,
    PanelSizeType,
)
from core.storage import StorageManager
from core.image_engine import (
    get_panel_dimensions,
    generate_panel_image,
    batch_generate_chapter_panels,
    estimate_generation_cost,
)
from providers.image_base import compute_image_cache_key
from providers.image_mock import MockImageProvider


@pytest.fixture
def sample_setup(tmp_path):
    storage = StorageManager(base_dir=tmp_path / "projects")
    settings = ProjectSettings(
        title="Living Ink",
        slug="living-ink",
        style_traits="High contrast black ink lineart, crisp screentones",
        chapters_per_volume=3,
    )
    storage.init_project_structure(settings)

    bible = Bible(
        logline="Living ink rebellion",
        synopsis="Full synopsis...",
        world_rules=["Living ink consumes stamina"],
        themes=["Honor"],
        characters=[
            CharacterSheet(
                name="Ren",
                role="Protagonist",
                visual_descriptor="Messy raven hair, amber eyes, black haori with rolled sleeves",
                personality="Reckless artist",
                motivation_arc="Avenge master",
            )
        ],
    )
    storage.save_bible(settings.slug, bible)

    script = ChapterScript(
        chapter_number=1,
        title="Blood on Parchment",
        summary="Opening chapter",
        pages=[
            PageScript(
                page_number=1,
                page_notes="Hook page",
                panels=[
                    PanelScript(
                        panel_number=1,
                        panel_size=PanelSizeType.WIDE,
                        camera_angle="Wide Establishing Shot",
                        description="Moonlit courtyard outside Kyoto temple",
                        characters_present=["Ren"],
                    ),
                    PanelScript(
                        panel_number=2,
                        panel_size=PanelSizeType.SMALL,
                        camera_angle="Close-up",
                        description="Ren's hand hovering over parchment with a calligraphy brush",
                        characters_present=["Ren"],
                    ),
                ],
            )
        ],
    )
    storage.save_chapter_script(settings.slug, 1, script)
    return storage, settings, bible, script


def test_mock_image_provider_generates_valid_png():
    provider = MockImageProvider()
    data = provider.generate("Test prompt", "no text", 512, 512, seed=42)
    assert isinstance(data, bytes)
    img = Image.open(io.BytesIO(data))
    assert img.size == (512, 512)
    assert img.format == "PNG"


def test_compute_cache_key_deterministic():
    k1 = compute_image_cache_key("A manga panel", 12345, 1024, 576)
    k2 = compute_image_cache_key("A manga panel", 12345, 1024, 576)
    k3 = compute_image_cache_key("A different panel", 12345, 1024, 576)
    assert k1 == k2
    assert k1 != k3


def test_generate_panel_image_and_cache(sample_setup):
    storage, settings, bible, script = sample_setup
    provider = MockImageProvider()
    panel = script.pages[0].panels[0]

    # First generation -> New image
    meta1, is_hit1 = generate_panel_image(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        page_number=1,
        panel=panel,
        bible=bible,
        settings=settings,
        provider=provider,
        seed=1001,
    )
    assert not is_hit1
    assert meta1.seed == 1001
    assert "no text, no speech bubbles, no lettering" in meta1.negative_prompt
    assert "Messy raven hair" in meta1.prompt  # Locked descriptor injected!

    # Verify image file exists
    img_path = storage.get_panel_image_path(settings.slug, 1, meta1.panel_id)
    assert img_path.exists()

    # Second generation with same seed -> Cache hit
    meta2, is_hit2 = generate_panel_image(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        page_number=1,
        panel=panel,
        bible=bible,
        settings=settings,
        provider=provider,
        seed=1001,
        force_refresh=False,
    )
    assert is_hit2
    assert meta2.cache_hash == meta1.cache_hash


def test_seed_locking(sample_setup):
    storage, settings, bible, script = sample_setup
    provider = MockImageProvider()
    panel = script.pages[0].panels[0]

    # Generate with locked seed
    meta, _ = generate_panel_image(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        page_number=1,
        panel=panel,
        bible=bible,
        settings=settings,
        provider=provider,
        seed=777777,
        seed_locked=True,
    )
    assert meta.seed_locked is True

    # Regenerate without passing seed -> should retain locked seed 777777
    meta_locked, _ = generate_panel_image(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        page_number=1,
        panel=panel,
        bible=bible,
        settings=settings,
        provider=provider,
        seed=None,
    )
    assert meta_locked.seed == 777777


def test_batch_generate_chapter_panels(sample_setup):
    storage, settings, bible, script = sample_setup
    provider = MockImageProvider()

    cost_estimate = estimate_generation_cost(storage, settings.slug, 1, script)
    assert cost_estimate["total_panels"] == 2
    assert cost_estimate["pending_calls"] == 2

    # Batch run
    results = batch_generate_chapter_panels(
        storage=storage,
        slug=settings.slug,
        chapter_number=1,
        script=script,
        bible=bible,
        settings=settings,
        provider=provider,
    )
    assert results["total"] == 2
    assert results["completed"] == 2
    assert results["new_generations"] == 2

    manifest = storage.load_panels_manifest(settings.slug, 1)
    assert "p1_panel1" in manifest.panels
    assert "p1_panel2" in manifest.panels

