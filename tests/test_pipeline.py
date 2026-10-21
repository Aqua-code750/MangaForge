import pytest
from core.models import ProjectSettings, ProjectMode, Bible, VolumePlan, ChapterScript
from core.pipeline import (
    generate_bible,
    generate_volume_plan,
    generate_chapter_script,
    generate_chapter_recap,
    build_panel_image_prompt,
    build_lettering_data_for_chapter,
    load_system_prompt,
)
from providers.text_mock import MockTextProvider


def test_load_system_prompt():
    prompt = load_system_prompt()
    assert "MANGAKA" in prompt or "manga" in prompt.lower()


def test_pipeline_stages_with_mock_provider():
    settings = ProjectSettings(
        title="Living Ink",
        slug="living-ink",
        genre="Dark Fantasy Shonen",
        style_traits="High contrast black ink lineart, crisp screentones",
        chapters_per_volume=5,
    )
    provider = MockTextProvider()

    # Stage 1: Bible
    bible = generate_bible(settings, "A boy uses living ink to fight the shogunate", provider)
    assert isinstance(bible, Bible)
    assert len(bible.characters) >= 1
    assert not bible.is_approved

    # Stage 2: Volume Plan
    volume_plan = generate_volume_plan(settings, bible, provider)
    assert isinstance(volume_plan, VolumePlan)
    assert len(volume_plan.chapters) == 5

    # Stage 3: Chapter Script
    script = generate_chapter_script(
        settings=settings,
        bible=bible,
        volume_plan=volume_plan,
        chapter_number=1,
        provider=provider,
        previous_recaps={},
    )
    assert isinstance(script, ChapterScript)
    assert script.chapter_number == 1
    assert len(script.pages) >= 1

    # Stage 3.5: Auto-generate Recap
    recap = generate_chapter_recap(script, provider)
    assert "recap" in recap.lower() or "ren" in recap.lower()

    # Stage 4: Panel Prompt Builder
    first_panel = script.pages[0].panels[0]
    prompt_bundle = build_panel_image_prompt(first_panel, bible, settings)
    assert "High contrast black ink" in prompt_bundle["prompt"]
    # Check universal negative prompt enforcing no text
    assert "no text, no speech bubbles, no lettering" in prompt_bundle["negative_prompt"]

    # Stage 5: Lettering data builder
    lettering = build_lettering_data_for_chapter(script)
    assert lettering["chapter_number"] == 1
    assert len(lettering["pages"]) == len(script.pages)

