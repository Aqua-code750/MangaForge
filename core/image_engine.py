from __future__ import annotations
import random
import time
from datetime import datetime
from typing import Optional, Dict, Tuple, List, Callable, Any
from pathlib import Path

from core.models import (
    ProjectSettings,
    ProjectMode,
    Bible,
    ChapterScript,
    PanelScript,
    PanelSizeType,
    PanelImageMetadata,
    ChapterPanelsManifest,
)
from core.storage import StorageManager
from core.pipeline import build_panel_image_prompt
from providers.image_base import ImageProvider, compute_image_cache_key


# Standard pixel dimensions optimized for Manga composition & diffusion models
PANEL_DIMENSIONS: Dict[PanelSizeType, Tuple[int, int]] = {
    PanelSizeType.SPLASH: (1024, 1448),  # Full-page manga ratio
    PanelSizeType.WIDE: (1024, 576),     # 16:9 cinematic horizontal
    PanelSizeType.TALL: (576, 1024),     # Vertical action / full body
    PanelSizeType.SMALL: (640, 640),     # Square reaction beat
}


def get_panel_dimensions(panel_size: PanelSizeType) -> Tuple[int, int]:
    """Return (width, height) in pixels for the given panel size type."""
    return PANEL_DIMENSIONS.get(panel_size, (1024, 576))


def estimate_generation_cost(
    storage: StorageManager,
    slug: str,
    chapter_number: int,
    script: ChapterScript,
) -> Dict[str, int]:
    """
    Cost-Guard helper: counts total panels in script, how many are already
    generated or cached, and how many new API calls would be executed.
    """
    manifest = storage.load_panels_manifest(slug, chapter_number)
    total_panels = sum(len(page.panels) for page in script.pages)
    existing_panels = 0

    for page in script.pages:
        for panel in page.panels:
            panel_id = f"p{page.page_number}_panel{panel.panel_number}"
            img_path = storage.get_panel_image_path(slug, chapter_number, panel_id)
            if img_path.exists() and panel_id in manifest.panels:
                existing_panels += 1

    pending_calls = max(0, total_panels - existing_panels)
    return {
        "total_panels": total_panels,
        "existing_panels": existing_panels,
        "pending_calls": pending_calls,
    }


def generate_panel_image(
    storage: StorageManager,
    slug: str,
    chapter_number: int,
    page_number: int,
    panel: PanelScript,
    bible: Bible,
    settings: ProjectSettings,
    provider: ImageProvider,
    seed: Optional[int] = None,
    seed_locked: bool = False,
    prompt_override: Optional[str] = None,
    force_refresh: bool = False,
) -> Tuple[PanelImageMetadata, bool]:
    """
    Generate or retrieve a cached panel illustration.
    Returns: (metadata: PanelImageMetadata, is_cache_hit: bool)
    """
    panel_id = f"p{page_number}_panel{panel.panel_number}"
    width, height = get_panel_dimensions(panel.panel_size)

    # 1. Enriched Prompt Compilation
    if prompt_override and prompt_override.strip():
        final_prompt = prompt_override.strip()
        negative_prompt = (
            "text, speech bubble, dialogue, words, lettering, subtitles, watermark, logo, signature, "
            "photorealistic, bad anatomy, deformed limbs, blurry, no text, no speech bubbles, no lettering"
        )
    else:
        prompt_bundle = build_panel_image_prompt(panel, bible, settings)
        final_prompt = prompt_bundle["prompt"]
        negative_prompt = prompt_bundle["negative_prompt"]

    # 2. Seed handling
    manifest = storage.load_panels_manifest(slug, chapter_number)
    existing_meta = manifest.panels.get(panel_id)

    if seed is None:
        if existing_meta and existing_meta.seed_locked and existing_meta.seed is not None:
            seed = existing_meta.seed
            seed_locked = True
        elif existing_meta and existing_meta.seed is not None and not force_refresh:
            seed = existing_meta.seed
        else:
            seed = random.randint(100000, 999999)

    # 3. SHA-256 Cache Key Calculation
    cache_hash = compute_image_cache_key(final_prompt, seed, width, height)
    image_filename = f"{panel_id}.png"
    target_img_path = storage.get_panel_image_path(slug, chapter_number, panel_id)

    # 4. Cache Lookup (Zero Cost Rerun)
    if not force_refresh:
        cached_bytes = storage.get_cached_image_bytes(slug, cache_hash)
        if cached_bytes is not None:
            storage.save_panel_image(slug, chapter_number, panel_id, cached_bytes)
            metadata = PanelImageMetadata(
                panel_id=panel_id,
                page_number=page_number,
                panel_number=panel.panel_number,
                prompt=final_prompt,
                negative_prompt=negative_prompt,
                width=width,
                height=height,
                seed=seed,
                seed_locked=seed_locked,
                cache_hash=cache_hash,
                image_filename=image_filename,
                status="generated",
                created_at=datetime.now().isoformat(),
            )
            manifest.panels[panel_id] = metadata
            storage.save_panels_manifest(slug, chapter_number, manifest)
            return metadata, True

    # 5. Generate New Panel Image via Provider
    img_bytes = provider.generate(
        prompt=final_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
    )

    # 6. Save to Cache and Chapter Panels Folder
    storage.save_cached_image_bytes(slug, cache_hash, img_bytes)
    storage.save_panel_image(slug, chapter_number, panel_id, img_bytes)

    # 7. Update Manifest
    metadata = PanelImageMetadata(
        panel_id=panel_id,
        page_number=page_number,
        panel_number=panel.panel_number,
        prompt=final_prompt,
        negative_prompt=negative_prompt,
        width=width,
        height=height,
        seed=seed,
        seed_locked=seed_locked,
        cache_hash=cache_hash,
        image_filename=image_filename,
        status="generated",
        created_at=datetime.now().isoformat(),
    )
    manifest.panels[panel_id] = metadata
    storage.save_panels_manifest(slug, chapter_number, manifest)

    return metadata, False


def batch_generate_chapter_panels(
    storage: StorageManager,
    slug: str,
    chapter_number: int,
    script: ChapterScript,
    bible: Bible,
    settings: ProjectSettings,
    provider: ImageProvider,
    force_refresh: bool = False,
    progress_callback: Optional[Callable[[int, int, str], None]] = None,
) -> Dict[str, Any]:
    """
    Batch generate all panels in a chapter script with progress reporting and cache checks.
    """
    total_panels = sum(len(page.panels) for page in script.pages)
    completed = 0
    cache_hits = 0
    new_generations = 0

    manifest = storage.load_panels_manifest(slug, chapter_number)

    for page in script.pages:
        for panel in page.panels:
            panel_id = f"p{page.page_number}_panel{panel.panel_number}"
            existing = manifest.panels.get(panel_id)

            # Skip already generated panels if not forcing refresh
            if not force_refresh and existing:
                img_path = storage.get_panel_image_path(slug, chapter_number, panel_id)
                if img_path.exists():
                    completed += 1
                    cache_hits += 1
                    if progress_callback:
                        progress_callback(completed, total_panels, f"Panel {panel_id} already generated (cached)")
                    continue

            seed = existing.seed if existing and existing.seed_locked else None
            locked = existing.seed_locked if existing else False

            meta, is_hit = generate_panel_image(
                storage=storage,
                slug=slug,
                chapter_number=chapter_number,
                page_number=page.page_number,
                panel=panel,
                bible=bible,
                settings=settings,
                provider=provider,
                seed=seed,
                seed_locked=locked,
                force_refresh=force_refresh,
            )

            completed += 1
            if is_hit:
                cache_hits += 1
            else:
                new_generations += 1

            if progress_callback:
                progress_callback(completed, total_panels, f"Finished {panel_id} ({'cache hit' if is_hit else 'new'})")

    return {
        "total": total_panels,
        "completed": completed,
        "cache_hits": cache_hits,
        "new_generations": new_generations,
    }

