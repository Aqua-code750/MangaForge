import pytest
import shutil
from pathlib import Path
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
)
from core.storage import StorageManager, slugify


@pytest.fixture
def temp_storage(tmp_path):
    mgr = StorageManager(base_dir=tmp_path / "projects")
    return mgr


def test_slugify():
    assert slugify("Shadows of Neo-Tokyo!!") == "shadows-of-neo-tokyo"
    assert slugify("  Dragon & Blade   ") == "dragon-blade"
    assert slugify("") == "manga-project"


def test_project_init_and_storage(temp_storage):
    settings = ProjectSettings(
        title="Spirit Blade",
        slug="spirit-blade",
        genre="Shonen",
        chapters_per_volume=3,
    )
    pdir = temp_storage.init_project_structure(settings)
    assert pdir.exists()
    assert (pdir / "settings.json").exists()
    assert (pdir / "chapters" / "ch01" / "panels").exists()
    assert (pdir / "chapters" / "ch03" / "pages").exists()
    assert "spirit-blade" in temp_storage.list_projects()

    loaded_settings = temp_storage.load_settings("spirit-blade")
    assert loaded_settings is not None
    assert loaded_settings.title == "Spirit Blade"


def test_bible_and_recap_persistence(temp_storage):
    settings = ProjectSettings(title="Spirit Blade", slug="spirit-blade")
    temp_storage.init_project_structure(settings)

    bible = Bible(
        logline="A blade awakened by spirit blood.",
        synopsis="Full volume narrative...",
        world_rules=["Spirits fade in sunlight"],
        themes=["Honor"],
        characters=[
            CharacterSheet(
                name="Ken",
                role="Protagonist",
                visual_descriptor="Scar over left eye, braided white hair",
                personality="Stoic",
                motivation_arc="Protect family",
            )
        ],
    )
    temp_storage.save_bible("spirit-blade", bible)
    loaded_bible = temp_storage.load_bible("spirit-blade")
    assert loaded_bible is not None
    assert loaded_bible.characters[0].name == "Ken"

    # Test chapter recap saving & retrieving
    temp_storage.save_chapter_recap("spirit-blade", 1, "Ken defeated the shadow demon.")
    temp_storage.save_chapter_recap("spirit-blade", 2, "Ken reached the iron fortress.")

    recaps = temp_storage.get_all_previous_recaps("spirit-blade", 3)
    assert len(recaps) == 2
    assert "shadow demon" in recaps[1]
    assert "iron fortress" in recaps[2]

