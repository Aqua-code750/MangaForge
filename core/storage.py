from __future__ import annotations
import json
import re
from pathlib import Path
from typing import List, Optional, Dict

from core.models import (
    ProjectSettings,
    Bible,
    VolumePlan,
    ChapterScript,
    ChapterPanelsManifest,
    PanelImageMetadata,
)

BASE_PROJECTS_DIR = Path("projects")


def slugify(text: str) -> str:
    """Convert text to a safe filesystem slug."""
    text = text.strip().lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[\s_-]+", "-", text)
    return text.strip("-") or "manga-project"


class StorageManager:
    """Handles folder structure and JSON/MD persistence for MangaForge projects."""

    def __init__(self, base_dir: Path = BASE_PROJECTS_DIR):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def list_projects(self) -> List[str]:
        """Return list of existing project slugs."""
        if not self.base_dir.exists():
            return []
        slugs = []
        for p in sorted(self.base_dir.iterdir()):
            if p.is_dir() and (p / "settings.json").exists():
                slugs.append(p.name)
        return slugs

    def get_project_dir(self, slug: str) -> Path:
        return self.base_dir / slug

    def init_project_structure(self, settings: ProjectSettings) -> Path:
        """Create the directory skeleton for a new project."""
        pdir = self.get_project_dir(settings.slug)
        pdir.mkdir(parents=True, exist_ok=True)
        (pdir / "chapters").mkdir(exist_ok=True)
        (pdir / "exports").mkdir(exist_ok=True)

        # Pre-create chapter directories
        for ch_idx in range(1, settings.chapters_per_volume + 1):
            ch_slug = f"ch{ch_idx:02d}"
            ch_dir = pdir / "chapters" / ch_slug
            ch_dir.mkdir(parents=True, exist_ok=True)
            (ch_dir / "panels").mkdir(exist_ok=True)
            (ch_dir / "pages").mkdir(exist_ok=True)

        self.save_settings(settings.slug, settings)
        return pdir

    # --- Settings ---
    def load_settings(self, slug: str) -> Optional[ProjectSettings]:
        path = self.get_project_dir(slug) / "settings.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ProjectSettings.model_validate(data)

    def save_settings(self, slug: str, settings: ProjectSettings) -> None:
        pdir = self.get_project_dir(slug)
        pdir.mkdir(parents=True, exist_ok=True)
        path = pdir / "settings.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(settings.model_dump_json(indent=2))

    # --- Bible ---
    def load_bible(self, slug: str) -> Optional[Bible]:
        path = self.get_project_dir(slug) / "bible.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return Bible.model_validate(data)

    def save_bible(self, slug: str, bible: Bible) -> None:
        pdir = self.get_project_dir(slug)
        pdir.mkdir(parents=True, exist_ok=True)
        path = pdir / "bible.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(bible.model_dump_json(indent=2))

    # --- Volume Plan ---
    def load_volume_plan(self, slug: str) -> Optional[VolumePlan]:
        path = self.get_project_dir(slug) / "volume_plan.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return VolumePlan.model_validate(data)

    def save_volume_plan(self, slug: str, volume_plan: VolumePlan) -> None:
        pdir = self.get_project_dir(slug)
        pdir.mkdir(parents=True, exist_ok=True)
        path = pdir / "volume_plan.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(volume_plan.model_dump_json(indent=2))

    # --- Chapters ---
    def get_chapter_dir(self, slug: str, chapter_number: int) -> Path:
        ch_slug = f"ch{chapter_number:02d}"
        ch_dir = self.get_project_dir(slug) / "chapters" / ch_slug
        ch_dir.mkdir(parents=True, exist_ok=True)
        (ch_dir / "panels").mkdir(exist_ok=True)
        (ch_dir / "pages").mkdir(exist_ok=True)
        return ch_dir

    def load_chapter_script(self, slug: str, chapter_number: int) -> Optional[ChapterScript]:
        path = self.get_chapter_dir(slug, chapter_number) / "script.json"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return ChapterScript.model_validate(data)

    def save_chapter_script(self, slug: str, chapter_number: int, script: ChapterScript) -> None:
        ch_dir = self.get_chapter_dir(slug, chapter_number)
        path = ch_dir / "script.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(script.model_dump_json(indent=2))

    def load_chapter_recap(self, slug: str, chapter_number: int) -> Optional[str]:
        path = self.get_chapter_dir(slug, chapter_number) / "recap.md"
        if not path.exists():
            return None
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def save_chapter_recap(self, slug: str, chapter_number: int, recap_content: str) -> None:
        ch_dir = self.get_chapter_dir(slug, chapter_number)
        path = ch_dir / "recap.md"
        with open(path, "w", encoding="utf-8") as f:
            f.write(recap_content)

    def get_all_previous_recaps(self, slug: str, current_chapter_number: int) -> Dict[int, str]:
        """Load recap.md of all chapters prior to current_chapter_number."""
        recaps: Dict[int, str] = {}
        for ch in range(1, current_chapter_number):
            content = self.load_chapter_recap(slug, ch)
            if content:
                recaps[ch] = content
            else:
                # If script exists without recap, fall back to script summary
                script = self.load_chapter_script(slug, ch)
                if script:
                    recaps[ch] = f"**Chapter {ch}: {script.title}**\n{script.summary}"
        return recaps

    # --- Panels & Image Cache ---
    def get_panels_dir(self, slug: str, chapter_number: int) -> Path:
        pdir = self.get_chapter_dir(slug, chapter_number) / "panels"
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def get_cache_dir(self, slug: str) -> Path:
        cdir = self.get_project_dir(slug) / ".cache" / "images"
        cdir.mkdir(parents=True, exist_ok=True)
        return cdir

    def get_cached_image_bytes(self, slug: str, cache_hash: str) -> Optional[bytes]:
        cpath = self.get_cache_dir(slug) / f"{cache_hash}.png"
        if cpath.exists():
            with open(cpath, "rb") as f:
                return f.read()
        return None

    def save_cached_image_bytes(self, slug: str, cache_hash: str, data: bytes) -> Path:
        cpath = self.get_cache_dir(slug) / f"{cache_hash}.png"
        with open(cpath, "wb") as f:
            f.write(data)
        return cpath

    def get_panel_image_path(self, slug: str, chapter_number: int, panel_id: str) -> Path:
        return self.get_panels_dir(slug, chapter_number) / f"{panel_id}.png"

    def save_panel_image(self, slug: str, chapter_number: int, panel_id: str, data: bytes) -> Path:
        out_path = self.get_panel_image_path(slug, chapter_number, panel_id)
        with open(out_path, "wb") as f:
            f.write(data)
        return out_path

    def load_panels_manifest(self, slug: str, chapter_number: int) -> ChapterPanelsManifest:
        path = self.get_panels_dir(slug, chapter_number) / "manifest.json"
        if not path.exists():
            return ChapterPanelsManifest(chapter_number=chapter_number, panels={})
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return ChapterPanelsManifest.model_validate(data)
        except Exception:
            return ChapterPanelsManifest(chapter_number=chapter_number, panels={})

    def save_panels_manifest(self, slug: str, chapter_number: int, manifest: ChapterPanelsManifest) -> None:
        path = self.get_panels_dir(slug, chapter_number) / "manifest.json"
        with open(path, "w", encoding="utf-8") as f:
            f.write(manifest.model_dump_json(indent=2))

    # --- Composed Pages & Lettering Data ---
    def get_pages_dir(self, slug: str, chapter_number: int) -> Path:
        pdir = self.get_chapter_dir(slug, chapter_number) / "pages"
        pdir.mkdir(parents=True, exist_ok=True)
        return pdir

    def get_lettering_path(self, slug: str, chapter_number: int, page_number: int) -> Path:
        return self.get_pages_dir(slug, chapter_number) / f"page_{page_number:02d}_lettering.json"

    def load_page_lettering(self, slug: str, chapter_number: int, page_number: int) -> Optional[Dict[str, Any]]:
        path = self.get_lettering_path(slug, chapter_number, page_number)
        if not path.exists():
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def save_page_lettering(self, slug: str, chapter_number: int, page_number: int, data: Dict[str, Any]) -> None:
        path = self.get_lettering_path(slug, chapter_number, page_number)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def get_composed_page_path(self, slug: str, chapter_number: int, page_number: int) -> Path:
        return self.get_pages_dir(slug, chapter_number) / f"page_{page_number:02d}.png"

