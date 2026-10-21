from __future__ import annotations
from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ProjectMode(str, Enum):
    PRINT = "PRINT"
    WEBTOON = "WEBTOON"
    BOTH = "BOTH"


class PanelSizeType(str, Enum):
    SPLASH = "splash"
    WIDE = "wide"
    TALL = "tall"
    SMALL = "small"


class BubbleType(str, Enum):
    SPEECH = "speech"
    THOUGHT = "thought"
    SHOUT = "shout"
    WHISPER = "whisper"
    SFX = "sfx"
    NARRATOR = "narrator"


class DialogueItem(BaseModel):
    speaker: str = Field(..., description="Character name or 'Narrator' or 'SFX'")
    text: str = Field(..., description="Spoken dialogue or SFX sound word (e.g. 'DON!')")
    type: BubbleType = Field(default=BubbleType.SPEECH, description="Type of bubble or sound effect")
    tail_position: Optional[str] = Field(default="bottom-center", description="Anchor direction: top-left, bottom-center, etc.")
    sfx_intensity: Optional[str] = Field(default=None, description="Low, Medium, Extreme for SFX")


class PanelScript(BaseModel):
    panel_number: int = Field(..., description="1-indexed panel number on page")
    panel_size: PanelSizeType = Field(default=PanelSizeType.WIDE, description="splash, wide, tall, small")
    camera_angle: str = Field(default="Medium Shot", description="Extreme Close-up, Close-up, Medium Shot, Long Shot, Dutch Angle, Bird's Eye, Worm's Eye")
    description: str = Field(..., description="Visual scene action, composition, expressions, lighting and environment")
    characters_present: List[str] = Field(default_factory=list, description="Names of characters appearing in this panel")
    dialogue: List[DialogueItem] = Field(default_factory=list, description="Dialogue bubbles and SFX on this panel")
    pacing_notes: Optional[str] = Field(default="", description="Rhythm, tension, or beat notes for the mangaka")


class PageScript(BaseModel):
    page_number: int = Field(..., description="1-indexed page number in the chapter")
    page_notes: Optional[str] = Field(default="", description="Layout goal, page-turn reveal, emotional rhythm")
    panels: List[PanelScript] = Field(..., description="List of panels on this page (typically 3-6 panels, splash is 1)")


class ChapterScript(BaseModel):
    chapter_number: int = Field(..., description="Chapter index (1, 2, ...)")
    title: str = Field(..., description="Chapter title")
    summary: str = Field(..., description="Brief 2-3 sentence chapter summary")
    pages: List[PageScript] = Field(..., description="Pages comprising the chapter")
    is_approved: bool = Field(default=False, description="Whether approved by user")


class CharacterSheet(BaseModel):
    name: str = Field(..., description="Character full name")
    role: str = Field(..., description="Protagonist, Rival, Antagonist, Mentor, Ally, Supporting")
    visual_descriptor: str = Field(
        ...,
        description="Locked visual descriptor: exact clothing, hairstyle, hair color, facial features/scars, body build, silhouettes for prompt injection"
    )
    personality: str = Field(..., description="Core personality traits and quirks")
    motivation_arc: str = Field(..., description="Internal goal, trauma, or progression across the volume")
    reference_images: List[str] = Field(default_factory=list, description="File paths or URLs of reference artwork")


class Bible(BaseModel):
    logline: str = Field(..., description="One-sentence hook summarizing protagonist, inciting incident, and ultimate stakes")
    synopsis: str = Field(..., description="Narrative synopsis for the entire volume")
    world_rules: List[str] = Field(..., description="Key worldbuilding rules, magic system / tech constraints, societal taboos")
    themes: List[str] = Field(..., description="Core themes (e.g. Sacrifice, Ambition, Identity, Survival)")
    characters: List[CharacterSheet] = Field(..., description="Character sheets with locked visual descriptors")
    visual_style_guide: str = Field(
        default="High-contrast black & white Japanese manga, crisp inking, dynamic screentones, expressive eyes",
        description="Overarching visual style prompt component"
    )
    is_approved: bool = Field(default=False, description="Whether approved by user")


class ChapterPlan(BaseModel):
    chapter_number: int = Field(..., description="1-indexed chapter number")
    title: str = Field(..., description="Title of the chapter")
    target_pages: int = Field(default=16, description="Target page count (e.g. 15-20 pages)")
    story_arc_goal: str = Field(..., description="What must happen or change by the end of this chapter")
    conflict: str = Field(..., description="Core obstacle, opponent, or emotional friction")
    climax_cliffhanger: str = Field(..., description="The climax or cliffhanger ending the chapter")


class VolumePlan(BaseModel):
    volume_number: int = Field(default=1, description="Volume index")
    volume_title: str = Field(..., description="Overarching title of this volume arc")
    volume_logline: str = Field(..., description="Summary of the volume's complete arc")
    pacing_outline: str = Field(..., description="Pacing structure (e.g. 3-act or Kishōtenketsu distribution across chapters)")
    chapters: List[ChapterPlan] = Field(..., description="Breakdown of chapters in this volume")
    is_approved: bool = Field(default=False, description="Whether approved by user")


class ProjectSettings(BaseModel):
    title: str = Field(..., description="Manga title")
    slug: str = Field(..., description="Filesystem directory slug (e.g. 'cyber-ronin')")
    genre: str = Field(default="Dark Fantasy Shonen", description="Genre or demographic")
    rating: str = Field(default="Teen (13+)", description="Content rating")
    mode: ProjectMode = Field(default=ProjectMode.BOTH, description="PRINT, WEBTOON, or BOTH")
    style_traits: str = Field(
        default="Master manga line art, high contrast screentone shading, sharp ink strokes, cinematic paneling, authentic Japanese manga style",
        description="Locked style traits passed to image generator"
    )
    trim_size: str = Field(default="128x182 mm (B6 Tankobon)", description="Print trim size")
    trim_width_mm: float = Field(default=128.0)
    trim_height_mm: float = Field(default=182.0)
    bleed_mm: float = Field(default=3.0, description="Bleed margin in mm")
    safe_margin_mm: float = Field(default=10.0, description="Inner text safe margin in mm")
    dpi: int = Field(default=300, description="Print DPI")
    chapters_per_volume: int = Field(default=5, description="Number of chapters in this volume")
    reading_direction: str = Field(default="RTL", description="RTL (Right-to-Left standard manga) or LTR (Left-to-Right)")


class PanelImageMetadata(BaseModel):
    panel_id: str = Field(..., description="Unique panel ID (e.g. 'p1_panel1')")
    page_number: int = Field(..., description="1-indexed page number")
    panel_number: int = Field(..., description="1-indexed panel number on page")
    prompt: str = Field(..., description="Final compiled positive prompt with style + character descriptors")
    negative_prompt: str = Field(..., description="Negative prompt enforcing no text/bubbles")
    width: int = Field(..., description="Width in pixels")
    height: int = Field(..., description="Height in pixels")
    seed: Optional[int] = Field(default=None, description="Generation seed")
    seed_locked: bool = Field(default=False, description="Whether seed is locked against random regeneration")
    cache_hash: str = Field(..., description="SHA-256 hash of (prompt, seed, size)")
    image_filename: str = Field(..., description="Filename in panels/ folder (e.g. 'p1_panel1.png')")
    status: str = Field(default="generated", description="'generated' or 'pending'")
    created_at: Optional[str] = Field(default=None, description="ISO timestamp")


class ChapterPanelsManifest(BaseModel):
    chapter_number: int = Field(..., description="1-indexed chapter number")
    panels: Dict[str, PanelImageMetadata] = Field(default_factory=dict, description="Map of panel_id -> metadata")


