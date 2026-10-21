from __future__ import annotations
import os
import json
import re
from typing import Type, TypeVar, Optional, List, Dict, Any
from pydantic import BaseModel, ValidationError
from dotenv import load_dotenv

from providers.text_base import TextProvider

load_dotenv()

T = TypeVar("T", bound=BaseModel)


def clean_json_string(raw: str) -> str:
    """Extract JSON object or array from markdown code fences or raw text."""
    raw = raw.strip()
    # Match ```json ... ``` or ``` ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", raw)
    if match:
        return match.group(1).strip()
    # Or find outermost { ... } or [ ... ]
    first_brace = raw.find("{")
    last_brace = raw.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return raw[first_brace : last_brace + 1].strip()
    return raw


class AnthropicTextProvider(TextProvider):
    """Claude text provider via Anthropic SDK with automated Pydantic schema validation & retry loop."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or os.getenv("ANTHROPIC_MODEL", "claude-3-7-sonnet-20250219")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "ANTHROPIC_API_KEY is missing. Please set it in your .env file or enter it in the app sidebar."
                )
            import anthropic
            self._client = anthropic.Anthropic(api_key=self.api_key)
        return self._client

    def generate_text(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4000,
    ) -> str:
        messages = [{"role": "user", "content": prompt}]
        kwargs: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            kwargs["system"] = system_prompt

        response = self.client.messages.create(**kwargs)
        # Anthropic response blocks
        content_parts = []
        for block in response.content:
            if hasattr(block, "text"):
                content_parts.append(block.text)
        return "\n".join(content_parts)

    def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.7,
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
        messages: List[Dict[str, str]] = [{"role": "user", "content": full_prompt}]

        last_error = None
        for attempt in range(max_retries + 1):
            kwargs: Dict[str, Any] = {
                "model": self.model,
                "messages": messages,
                "max_tokens": 4096,
                "temperature": temperature,
            }
            if system_prompt:
                kwargs["system"] = system_prompt

            response = self.client.messages.create(**kwargs)
            raw_text = "".join(b.text for b in response.content if hasattr(b, "text"))
            cleaned = clean_json_string(raw_text)

            try:
                data = json.loads(cleaned)
                validated = response_model.model_validate(data)
                return validated
            except (json.JSONDecodeError, ValidationError) as e:
                last_error = e
                if attempt < max_retries:
                    err_msg = str(e)
                    # Feed error back to the assistant turn
                    messages.append({"role": "assistant", "content": raw_text})
                    messages.append(
                        {
                            "role": "user",
                            "content": (
                                f"Validation failed on attempt {attempt + 1}/{max_retries + 1}:\n{err_msg}\n\n"
                                f"Please fix the formatting and schema mismatches. "
                                f"Output strictly the corrected JSON adhering to the schema."
                            ),
                        }
                    )
                else:
                    raise ValueError(
                        f"Failed to generate valid {response_model.__name__} after {max_retries} retries. "
                        f"Last error: {last_error}\nRaw output:\n{raw_text[:500]}"
                    ) from e

