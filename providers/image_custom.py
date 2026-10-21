from __future__ import annotations
import os
import io
import re
import json
import base64
import logging
from typing import Optional, List
from PIL import Image, ImageDraw, ImageFont
from dotenv import load_dotenv

from providers.image_base import ImageProvider

load_dotenv()
logger = logging.getLogger(__name__)


def map_dimensions_to_aspect_ratio(width: int, height: int) -> str:
    """Map pixel dimensions to closest aspect ratio: 1:1, 3:4, 4:3, 9:16, 16:9."""
    ratio = width / height
    if ratio >= 1.6:
        return "16:9"
    elif ratio >= 1.2:
        return "4:3"
    elif 0.9 <= ratio <= 1.1:
        return "1:1"
    elif ratio <= 0.65:
        return "9:16"
    else:
        return "3:4"


def create_quota_cooldown_placeholder(width: int, height: int, prompt: str, notice: str) -> bytes:
    """Renders a high-contrast manga panel indicating API quota cooldown so pipeline does not break."""
    img = Image.new("RGB", (width, height), color=(250, 250, 250))
    draw = ImageDraw.Draw(img)

    # Outer border
    draw.rectangle([(8, 8), (width - 8, height - 8)], outline=(20, 20, 20), width=4)
    draw.rectangle([(16, 16), (width - 16, height - 16)], outline=(80, 80, 80), width=1)

    # Stylized banner
    banner_h = 70
    draw.rectangle([(16, 16), (width - 16, 16 + banner_h)], fill=(30, 30, 30))
    draw.text((28, 28), "⚡ GOOGLE GEMINI IMAGE ENGINE", fill=(255, 255, 255))
    draw.text((28, 50), "Free Tier Quota Cooldown Active", fill=(255, 200, 100))

    # Details
    draw.text((28, 105), notice[:90], fill=(180, 20, 20))
    if len(notice) > 90:
        draw.text((28, 125), notice[90:180], fill=(180, 20, 20))

    # Prompt preview
    draw.text((28, 160), "PANEL PROMPT:", fill=(50, 50, 50))
    words = prompt.split()
    lines = []
    curr = []
    for w in words:
        curr.append(w)
        if len(" ".join(curr)) > 45:
            lines.append(" ".join(curr))
            curr = []
    if curr:
        lines.append(" ".join(curr))

    y = 185
    for l in lines[:6]:
        draw.text((28, y), l, fill=(80, 80, 80))
        y += 20

    draw.text((28, height - 40), "💡 Switch to Mock Provider in sidebar or wait for daily reset.", fill=(120, 120, 120))

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class CustomImageProvider(ImageProvider):
    """
    Production Image AI Provider powered by google-generativeai (Google Gemini)
    and Google GenAI models (nano-banana-pro-preview, gemini-nano-banana-2.1, etc.).
    Includes automatic aspect-ratio mapping, negative prompting, and dimension resizing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = (
                os.getenv("IMAGE_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
                or ""
            )
        self.endpoint = endpoint or os.getenv("IMAGE_API_ENDPOINT", "")
        self.model_name = (
            model_name
            or os.getenv("IMAGE_MODEL_NAME")
            or "nano-banana-pro-preview"
        )
        self._configured = False

    def _ensure_configured(self):
        if not self.api_key:
            raise ValueError(
                "IMAGE_API_KEY / GEMINI_API_KEY is not configured in .env or the sidebar. "
                "Please add your Google AI Studio key."
            )
        if not self._configured:
            try:
                import google.generativeai as genai
                genai.configure(api_key=self.api_key)
                self._configured = True
            except Exception as e:
                logger.warning(f"google.generativeai configuration warning: {e}")

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
        Generate panel artwork using configured Google Generative AI (Gemini).
        Automatically scales and crops to target width x height.
        """
        self._ensure_configured()
        aspect_ratio = map_dimensions_to_aspect_ratio(width, height)

        # 1. Primary Method: google.generativeai multimodal / image models
        try:
            import google.generativeai as genai

            full_prompt = prompt
            if negative_prompt:
                full_prompt += f" (Exclude: {negative_prompt})"

            model_inst = genai.GenerativeModel(self.model_name)
            response = model_inst.generate_content(full_prompt)

            # Check for inline_data parts containing image bytes
            if hasattr(response, "candidates") and response.candidates:
                candidate = response.candidates[0]
                if hasattr(candidate, "content") and hasattr(candidate.content, "parts"):
                    for part in candidate.content.parts:
                        if hasattr(part, "inline_data") and part.inline_data:
                            raw_data = part.inline_data.data
                            # decode base64 if needed
                            if isinstance(raw_data, str):
                                raw_bytes = base64.b64decode(raw_data)
                            else:
                                raw_bytes = bytes(raw_data)

                            img = Image.open(io.BytesIO(raw_bytes))
                            if img.size != (width, height):
                                img = img.resize((width, height), Image.Resampling.LANCZOS)
                            buf = io.BytesIO()
                            img.save(buf, format="PNG")
                            return buf.getvalue()

        except Exception as e:
            err_str = str(e)
            if "ResourceExhausted" in err_str or "429" in err_str:
                logger.warning(f"Google Gemini Image Quota Exceeded (429): {err_str}")
                # Provide a high-contrast styled placeholder so batch generation does not crash
                return create_quota_cooldown_placeholder(
                    width=width,
                    height=height,
                    prompt=prompt,
                    notice=f"429 Quota Exceeded for {self.model_name}. Cooldown active.",
                )
            logger.info(f"google.generativeai image attempt: {e}. Trying fallback...")

        # 2. Secondary Method: google.genai Client (for Imagen models)
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key)
            config_args = {
                "number_of_images": 1,
                "aspect_ratio": aspect_ratio,
                "output_mime_type": "image/png",
            }
            if negative_prompt:
                config_args["negative_prompt"] = negative_prompt

            config = types.GenerateImagesConfig(**config_args)
            response = client.models.generate_images(
                model=self.model_name,
                prompt=prompt,
                config=config,
            )

            if response.generated_images and len(response.generated_images) > 0:
                raw_bytes = response.generated_images[0].image.image_bytes
                img = Image.open(io.BytesIO(raw_bytes))
                if img.size != (width, height):
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

        except Exception as genai_client_err:
            client_err_str = str(genai_client_err)
            if "ResourceExhausted" in client_err_str or "429" in client_err_str:
                return create_quota_cooldown_placeholder(
                    width=width,
                    height=height,
                    prompt=prompt,
                    notice=f"429 Quota Exceeded for {self.model_name}.",
                )
            logger.info(f"google.genai fallback note: {genai_client_err}. Trying REST...")

        # 3. Tertiary Method: REST endpoint fallback
        import requests

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model_name}:predict?key={self.api_key}"
        payload = {
            "instances": [{"prompt": prompt}],
            "parameters": {
                "sampleCount": 1,
                "aspectRatio": aspect_ratio,
                "negativePrompt": negative_prompt,
            },
        }
        try:
            res = requests.post(url, json=payload, timeout=60)
            if res.status_code == 200:
                data = res.json()
                b64_str = data["predictions"][0]["bytesBase64Encoded"]
                raw_bytes = base64.b64decode(b64_str)
                img = Image.open(io.BytesIO(raw_bytes))
                if img.size != (width, height):
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
            elif res.status_code == 429:
                return create_quota_cooldown_placeholder(
                    width=width,
                    height=height,
                    prompt=prompt,
                    notice=f"429 Free Tier Daily Limit on Google AI Studio for {self.model_name}.",
                )
            else:
                raise ValueError(f"HTTP {res.status_code}: {res.text}")
        except Exception as http_err:
            logger.warning(f"REST attempt failed: {http_err}")
            # Final graceful fallback to prevent blocking user's MangaForge experience
            return create_quota_cooldown_placeholder(
                width=width,
                height=height,
                prompt=prompt,
                notice=f"API Cooldown: {http_err}",
            )
