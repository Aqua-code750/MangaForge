from __future__ import annotations
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from pydantic import BaseModel

from core.models import (
    ProjectSettings,
    Bible,
    VolumePlan,
    ChapterPlan,
    ChapterScript,
    PanelScript,
    DialogueItem,
)
from providers.text_base import TextProvider

PROMPTS_DIR = Path("prompts")
SYSTEM_PROMPT_FILE = PROMPTS_DIR / "mangaka_system.md"


def load_system_prompt() -> str:
    """Load the mangaka system prompt from prompts/mangaka_system.md."""
    if SYSTEM_PROMPT_FILE.exists():
        with open(SYSTEM_PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read()
    return "You are an expert manga author and director."


# ==============================================================================
# STAGE 1: GENERATE BIBLE
# ==============================================================================
def generate_bible(
    settings: ProjectSettings,
    user_pitch: str,
    provider: TextProvider,
) -> Bible:
    """Generate the Manga Story Bible containing logline, world rules, and character sheets."""
    system_prompt = load_system_prompt()

    user_prompt = f"""
PROJECT METADATA:
- Title: {settings.title}
- Genre: {settings.genre}
- Target Rating: {settings.rating}
- Mode: {settings.mode.value}
- Visual Style Traits: {settings.style_traits}

CREATOR'S INITIAL PITCH & VISION:
{user_pitch}

TASK:
Craft a comprehensive, professional Manga Story Bible.
Create:
1. A gripping logline (protagonist + inciting incident + stakes).
2. A rich volume-length narrative synopsis.
3. 3-5 crucial world rules, limitations, and power/social dynamics.
4. Core themes explored throughout the manga.
5. In-depth character sheets (at least protagonist, key ally/tactician, and antagonist/rival).
   CRITICAL: For every character, write a highly specific, locked 'visual_descriptor' detailing exact hairstyle, clothing, distinctive markings, accessories, and silhouette. This descriptor will be injected directly into Image AI generation for visual consistency across every panel.
6. A cohesive visual style guide.

Ensure the output conforms strictly to the Bible schema.
"""
    bible = provider.generate_structured(
        prompt=user_prompt,
        response_model=Bible,
        system_prompt=system_prompt,
        temperature=0.7,
    )
    return bible


# ==============================================================================
# STAGE 2: GENERATE VOLUME PLAN
# ==============================================================================
def generate_volume_plan(
    settings: ProjectSettings,
    bible: Bible,
    provider: TextProvider,
    user_notes: str = "",
) -> VolumePlan:
    """Generate chapter-by-chapter volume pacing outline based on approved Bible."""
    system_prompt = load_system_prompt()

    char_summaries = "\n".join([f"- {c.name} ({c.role}): {c.personality}" for c in bible.characters])

    user_prompt = f"""
PROJECT: {settings.title} ({settings.genre}, {settings.rating})
LOGLINE: {bible.logline}
SYNOPSIS: {bible.synopsis}

CHARACTERS:
{char_summaries}

WORLD RULES:
{chr(10).join(f"- {rule}" for rule in bible.world_rules)}

VOLUME SPECIFICATIONS:
- Number of chapters in this volume: {settings.chapters_per_volume}
- Mode: {settings.mode.value}
- Additional creator notes: {user_notes or 'Follow standard Japanese manga volume pacing with a strong hook in Ch 1 and major climax/cliffhanger at volume finale.'}

TASK:
Design the complete Volume Plan broken down into exactly {settings.chapters_per_volume} chapters.
For each chapter specify:
1. `chapter_number` (1 to {settings.chapters_per_volume})
2. `title`
3. `target_pages` (standard 15-20 pages per chapter)
4. `story_arc_goal` (what changes permanently in this chapter)
5. `conflict` (primary antagonist/situational obstacle)
6. `climax_cliffhanger` (how the chapter ends on high tension to compel readers to turn to the next chapter)

Ensure the output conforms strictly to the VolumePlan schema.
"""
    volume_plan = provider.generate_structured(
        prompt=user_prompt,
        response_model=VolumePlan,
        system_prompt=system_prompt,
        temperature=0.7,
    )
    return volume_plan


# ==============================================================================
# STAGE 3: GENERATE CHAPTER SCRIPT
# ==============================================================================
def generate_chapter_script(
    settings: ProjectSettings,
    bible: Bible,
    volume_plan: VolumePlan,
    chapter_number: int,
    provider: TextProvider,
    previous_recaps: Optional[Dict[int, str]] = None,
    user_notes: str = "",
) -> ChapterScript:
    """
    Generate complete manga chapter script (pages, panels, dialogue, camera angles, SFX, pacing notes).
    Always includes Bible, Volume Plan, and all earlier chapter recaps.
    """
    system_prompt = load_system_prompt()

    # Find the chapter plan for this chapter
    target_plan: Optional[ChapterPlan] = None
    for cp in volume_plan.chapters:
        if cp.chapter_number == chapter_number:
            target_plan = cp
            break

    if target_plan is None:
        target_plan = ChapterPlan(
            chapter_number=chapter_number,
            title=f"Chapter {chapter_number}",
            target_pages=16,
            story_arc_goal="Advance the central conflict",
            conflict="Rising antagonism",
            climax_cliffhanger="Dramatic cliffhanger reveal",
        )

    # Format previous recaps
    recaps_text = ""
    if previous_recaps:
        recaps_blocks = []
        for ch_num, rcontent in sorted(previous_recaps.items()):
            recaps_blocks.append(f"### Chapter {ch_num} Recap:\n{rcontent}")
        recaps_text = "\n\n".join(recaps_blocks)
    else:
        recaps_text = "No previous chapters (This is Chapter 1 - Opening Chapter)."

    char_details = "\n".join(
        [f"- {c.name} ({c.role}): {c.visual_descriptor}" for c in bible.characters]
    )

    user_prompt = f"""
PROJECT: {settings.title} ({settings.genre})
READING DIRECTION: {settings.reading_direction} (Standard Japanese manga is Right-to-Left)
CURRENT CHAPTER: Chapter {chapter_number} - "{target_plan.title}"
TARGET PAGES: {target_plan.target_pages} (Generate a rich script with key representative pages showcasing full page-by-page pacing)
STORY ARC GOAL: {target_plan.story_arc_goal}
CENTRAL CONFLICT: {target_plan.conflict}
CHAPTER CLIMAX/CLIFFHANGER: {target_plan.climax_cliffhanger}

STORY BIBLE CONTEXT:
Logline: {bible.logline}
World Rules: {chr(10).join(f"- {r}" for r in bible.world_rules)}

CHARACTERS IN UNIVERSE:
{char_details}

VOLUME OUTLINE:
{volume_plan.pacing_outline}

PREVIOUS CHAPTER RECAPS (STORY CONTINUITY):
{recaps_text}

CREATOR'S SPECIFIC NOTES FOR THIS CHAPTER:
{user_notes or 'None provided. Adhere closely to the volume plan goal.'}

TASK:
Write the complete, highly detailed manga script for Chapter {chapter_number}.
Structure the chapter page by page:
- Each page must have 3-5 panels (or 1 for a dramatic splash page).
- Assign appropriate `panel_size` ('splash', 'wide', 'tall', 'small').
- Provide clear `camera_angle` (e.g. Extreme Close-up, Close-up, Low Angle, Dutch Angle, Wide Establishing Shot).
- Describe the visual composition, character expressions, lighting, and action vividly in `description`.
- List `characters_present` for every panel.
- Write punchy, authentic manga dialogue and expressive Japanese sound effects (SFX) with intensity levels.
- Include `pacing_notes` for panel tempo.

Ensure the output conforms strictly to the ChapterScript schema.
"""
    script = provider.generate_structured(
        prompt=user_prompt,
        response_model=ChapterScript,
        system_prompt=system_prompt,
        temperature=0.7,
    )
    return script


# ==============================================================================
# AUTO-GENERATE CHAPTER RECAP
# ==============================================================================
def generate_chapter_recap(
    script: ChapterScript,
    provider: TextProvider,
) -> str:
    """Summarize an approved chapter script into a concise recap.md for future chapter context."""
    system_prompt = (
        "You are an expert manga story editor. Create a sharp, bulleted summary of key narrative developments, "
        "character decisions, power reveals, and cliffhanger states."
    )

    prompt = f"""
Please generate a concise recap markdown document for Chapter {script.chapter_number}: "{script.title}".

Chapter Summary:
{script.summary}

Page & Panel Highlights:
{chr(10).join([f"Page {p.page_number}: {p.page_notes} ({len(p.panels)} panels)" for p in script.pages])}

Produce a clean Markdown recap formatted with:
- Key Narrative Events (bullet points)
- Character Relationship / State Changes
- Cliffhanger / Final Ending Status
"""
    return provider.generate_text(prompt=prompt, system_prompt=system_prompt)


# ==============================================================================
# STAGE 4: GENERATE PANEL PROMPTS (PREPARED FOR PHASE 2)
# ==============================================================================
def build_panel_image_prompt(
    panel: PanelScript,
    bible: Bible,
    settings: ProjectSettings,
) -> Dict[str, str]:
    """
    Constructs the automated, enriched prompt for the Image AI.
    Automatically combines:
      1. Locked style traits from settings
      2. Scene composition, camera angle, and panel description
      3. Locked visual descriptors for every character present
      4. Universal negative prompt enforcing 'no text, no speech bubbles, no lettering'
    """
    # 1. Base style
    style_part = settings.style_traits.strip()

    # 2. Composition and scene
    scene_part = f"{panel.camera_angle}, {panel.description}".strip()

    # 3. Locked character visual descriptors
    char_map = {c.name.lower(): c for c in bible.characters}
    char_descriptors = []
    for char_name in panel.characters_present:
        matched = char_map.get(char_name.lower())
        if matched:
            char_descriptors.append(f"{matched.name}: {matched.visual_descriptor}")
        else:
            char_descriptors.append(f"{char_name}")

    char_part = ""
    if char_descriptors:
        char_part = "Characters: " + "; ".join(char_descriptors)

    # Combine into positive prompt
    prompt_elements = [style_part, scene_part]
    if char_part:
        prompt_elements.append(char_part)

    final_positive_prompt = ", ".join(prompt_elements)

    # Universal manga negative prompt
    negative_prompt = (
        "text, speech bubble, dialogue, words, lettering, subtitles, watermark, logo, signature, "
        "photorealistic, bad anatomy, deformed limbs, blurry, extra fingers, no text, no speech bubbles, no lettering"
    )

    return {
        "prompt": final_positive_prompt,
        "negative_prompt": negative_prompt,
    }


# ==============================================================================
# STAGE 5: BUILD LETTERING DATA (PREPARED FOR PHASE 3)
# ==============================================================================
def build_lettering_data_for_chapter(script: ChapterScript) -> Dict[str, Any]:
    """
    Extract dialogue and lettering items into structured editable overlays.
    Enables moving and editing speech bubbles without regenerating artwork.
    """
    lettering_pages = []
    for page in script.pages:
        page_bubbles = []
        for panel in page.panels:
            for idx, d in enumerate(panel.dialogue):
                page_bubbles.append({
                    "panel_number": panel.panel_number,
                    "bubble_id": f"p{page.page_number}_panel{panel.panel_number}_b{idx+1}",
                    "speaker": d.speaker,
                    "text": d.text,
                    "type": d.type.value,
                    "tail_position": d.tail_position or "bottom-center",
                    "sfx_intensity": d.sfx_intensity,
                    # Normalized coordinates (0.0 to 1.0) for interactive dragging/nudging
                    "x_pct": 0.5,
                    "y_pct": 0.2 + (idx * 0.15),
                })
        lettering_pages.append({
            "page_number": page.page_number,
            "bubbles": page_bubbles,
        })
    return {
        "chapter_number": script.chapter_number,
        "title": script.title,
        "pages": lettering_pages,
    }

