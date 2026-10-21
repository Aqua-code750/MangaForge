from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class TextProvider(ABC):
    """Abstract base class for swappable LLM text generation providers."""

    @abstractmethod
    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        """Generate raw text response."""
        pass

    @abstractmethod
    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_retries: int = 2,
    ) -> T:
        """
        Generate structured output validated against a Pydantic model.
        If validation fails, retries up to max_retries feeding the validation error back.
        """
        pass

