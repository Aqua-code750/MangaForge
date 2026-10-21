import pytest
from core.models import (
    ProjectSettings,
    ProjectMode,
    Bible,
    CharacterSheet,
    VolumePlan,
    ChapterPlan,
    ChapterScript,
    PageScript,
    PanelScript,
    DialogueItem,
    PanelSizeType,
    BubbleType,
)


def test_project_settings_defaults():
    settings = ProjectSettings(title="Cyber Ronin", slug="cyber-ronin")
    assert settings.slug == "cyber-ronin"
    assert settings.mode == ProjectMode.BOTH
    assert settings.chapters_per_volume == 5
    assert settings.bleed_mm == 3.0
    assert settings.dpi == 300
    assert "Japanese" in settings.style_traits


def test_character_sheet_locked_descriptor():
    char = CharacterSheet(
        name="Ren",
        role="Protagonist",
        visual_descriptor="Messy black hair, amber eyes, torn haori",
        personality="Bold and reckless",
        motivation_arc="Avenge master",
    )
    assert char.name == "Ren"
    assert "amber eyes" in char.visual_descriptor


def test_chapter_script_validation():
    panel = PanelScript(
        panel_number=1,
        panel_size=PanelSizeType.SPLASH,
        description="Ren stands atop the pagoda under full moon",
        characters_present=["Ren"],
        dialogue=[
            DialogueItem(speaker="Ren", text="Tonight ends it all.", type=BubbleType.SHOUT)
        ],
    )
    page = PageScript(page_number=1, page_notes="Dramatic opener", panels=[panel])
    script = ChapterScript(
        chapter_number=1,
        title="Moonlit Strike",
        summary="Ren confronts the vanguard",
        pages=[page],
    )
    assert len(script.pages) == 1
    assert script.pages[0].panels[0].dialogue[0].type == BubbleType.SHOUT
    assert not script.is_approved

