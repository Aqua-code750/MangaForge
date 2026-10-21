from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any
import hashlib


def compute_image_cache_key(prompt: str, seed: Optional[int], width: int, height: int) -> str:
    """Generate SHA256 cache key based on prompt, seed, and dimensions."""
    key_src = f"{prompt}|{seed}|{width}x{height}"
    return hashlib.sha256(key_src.encode("utf-8")).hexdigest()


class ImageProvider(ABC):
    """Abstract interface for MangaForge image generation engines."""

    @abstractmethod
    def generate(
        self,
        prompt: str,
        negative_prompt: str,
        width: int,
        height: int,
        seed: Optional[int] = None,
        reference_images: Optional[List[str]] = None,
    ) -> bytes:
        """
        Generate a single panel illustration.
        Returns PNG bytes.
        """
        pass

