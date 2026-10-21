from __future__ import annotations
import os
import json
import re
import logging
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

from providers.text_base import TextProvider

load_dotenv()
logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


def clean_json_string(raw: str) -> str:
    """Extract JSON object or array from markdown code fences or raw text."""
    raw = raw.strip()
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if match:
        return match.group(1).strip()
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return raw[first_brace : last_brace + 1].strip()
    return raw


class GeminiTextProvider(TextProvider):
    """
    Google Gemini text provider powered by google-generativeai (with google.genai fallback).
    Includes Pydantic JSON schema enforcement and automated error-feedback retry loops.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = (
                os.getenv("GEMINI_API_KEY")
                or os.getenv("IMAGE_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
                or ""
            )
        self.model = model or os.getenv("GEMINI_MODEL", "gemini-3.8-flash")
        self._configured = False

    def _ensure_configured(self):
        if not self.api_key:
            raise ValueError(
                "GEMINI_API_KEY / GOOGLE_API_KEY is missing. "
                "Please configure it in .env or the MangaForge sidebar."
            )
        if not self._configured:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._configured = True
            except Exception as e:
                logger.warning(f"google.generativeai configure error: {e}")

    @property
    def client(self):
        self._ensure_configured()
        from google import genai
        return genai.Client(api_key=self.api_key)

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: int = 4000,
    ) -> str:
        self._ensure_configured()

        # Primary: google-generativeai
        try:
            import google.generativeai as genai

            model_kwargs = {"model_name": self.model}
            if system_prompt:
                model_kwargs["system_instruction"] = system_prompt

            model_instance = genai.GenerativeModel(**model_kwargs)

            config_kwargs: Dict[str, Any] = {"max_output_tokens": max_tokens}
            if temperature is not None:
                config_kwargs["temperature"] = temperature

            cfg = genai.types.GenerationConfig(**config_kwargs)
            res = model_instance.generate_content(prompt, generation_config=cfg)
            if hasattr(res, "text") and res.text:
                return res.text
            return ""
        except Exception as genai_err:
            logger.info(f"google-generativeai invocation note: {genai_err}. Trying google.genai fallback...")

        # Secondary: google.genai client fallback
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config_dict: Dict[str, Any] = {"max_output_tokens": max_tokens}
            if temperature is not None:
                config_dict["temperature"] = temperature
            if system_prompt:
                config_dict["system_instruction"] = system_prompt

            config = types.GenerateContentConfig(**config_dict)
            response = client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )
            return response.text or ""
        except Exception as e:
            raise RuntimeError(f"Gemini text generation failed: {e}") from e

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: Optional[float] = None,
        max_retries: int = 2,
    ) -> T:
        schema = json.dumps(response_model.model_json_schema(), indent=2)
        guidance = (
            f"\n\nYou MUST respond ONLY with a single valid JSON object that conforms strictly to this JSON schema:\n"
            f"```json\n{schema}\n```\n"
            f"Do not include any greeting, preamble, markdown outside the JSON, or conversational filler. "
            f"Output only the JSON."
        )

        full_prompt = prompt + guidance
        last_error = None

        for attempt in range(max_retries + 1):
            try:
                raw_text = self.generate_text(
                    prompt=full_prompt,
                    system_prompt=system_prompt,
                    temperature=temperature,
                    max_tokens=4096,
                )
                cleaned = clean_json_string(raw_text)
                data = json.loads(cleaned)
                validated = response_model.model_validate(data)
                return validated
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                if attempt < max_retries:
                    err_msg = str(e)
                    full_prompt += (
                        f"\n\nValidation error on attempt {attempt+1}:\n{err_msg}\n"
                        f"Please fix the error and output strictly the valid JSON object conforming to the schema."
                    )
                else:
                    raise ValueError(
                        f"Failed to generate valid {response_model.__name__} with Gemini after {max_retries} retries. "
                        f"Last error: {last_error}"
                    ) from e
