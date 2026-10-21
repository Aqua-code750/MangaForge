from __future__ import annotations
import os
import io
import json
import logging
from typing import Optional, List
from PIL import Image
from dotenv import load_dotenv

from providers.image_base import ImageProvider

load_dotenv()
logger = logging.getLogger(__name__)


def map_dimensions_to_aspect_ratio(width: int, height: int) -> str:
    """Map pixel dimensions to closest Imagen aspect ratio: 1:1, 3:4, 4:3, 9:16, 16:9."""
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


class CustomImageProvider(ImageProvider):
    """
    Production Image AI Provider powered by Gemini / Imagen 3 (Google GenAI)
    with automated aspect-ratio mapping, negative prompting, and dimension resizing.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        model_name: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            or os.getenv("IMAGE_API_KEY")
            or os.getenv("GEMINI_API_KEY")
            or ""
        )
        self.endpoint = endpoint or os.getenv("IMAGE_API_ENDPOINT", "")
        self.model_name = model_name or os.getenv("IMAGE_MODEL_NAME", "imagen-3.0-generate-002")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            if not self.api_key:
                raise ValueError(
                    "IMAGE_API_KEY or GEMINI_API_KEY is not configured in .env or settings."
                )
            from google import genai
            self._client = genai.Client(api_key=self.api_key)
        return self._client

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
        Generate panel artwork using Gemini / Imagen 3 API.
        Automatically scales and crops to target width x height if needed.
        """
        if not self.api_key:
            raise ValueError(
                "Cannot generate image: IMAGE_API_KEY / GEMINI_API_KEY is missing. "
                "Please set it in .env or the MangaForge sidebar."
            )

        aspect_ratio = map_dimensions_to_aspect_ratio(width, height)

        try:
            from google.genai import types

            config_args = {
                "number_of_images": 1,
                "aspect_ratio": aspect_ratio,
                "output_mime_type": "image/png",
            }
            # Negative prompt if supported
            if negative_prompt:
                config_args["negative_prompt"] = negative_prompt

            config = types.GenerateImagesConfig(**config_args)

            response = self.client.models.generate_images(
                model=self.model_name,
                prompt=prompt,
                config=config,
            )

            if response.generated_images and len(response.generated_images) > 0:
                raw_bytes = response.generated_images[0].image.image_bytes

                # Resize / fit to exact requested panel dimensions if aspect ratio differs slightly
                img = Image.open(io.BytesIO(raw_bytes))
                if img.size != (width, height):
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

            raise ValueError("No images returned from Gemini/Imagen API response.")

        except Exception as e:
            logger.error(f"Gemini/Imagen generation failed: {e}. Falling back to REST call.")
            # Fallback to direct HTTP request in case the SDK version differs
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
                    import base64
                    data = res.json()
                    b64_str = data["predictions"][0]["bytesBase64Encoded"]
                    raw_bytes = base64.b64decode(b64_str)
                    img = Image.open(io.BytesIO(raw_bytes))
                    if img.size != (width, height):
                        img = img.resize((width, height), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue()
                else:
                    raise ValueError(f"HTTP error {res.status_code}: {res.text}")
            except Exception as http_err:
                raise RuntimeError(
                    f"Gemini Imagen image generation failed with error: {e} | HTTP error: {http_err}"
                ) from e

        try:
            from google.genai import types

            config_args = {
                "number_of_images": 1,
                "aspect_ratio": aspect_ratio,
                "output_mime_type": "image/png",
            }
            # Negative prompt if supported
            if negative_prompt:
                config_args["negative_prompt"] = negative_prompt

            config = types.GenerateImagesConfig(**config_args)

            response = self.client.models.generate_images(
                model=self.model_name,
                prompt=prompt,
                config=config,
            )

            if response.generated_images and len(response.generated_images) > 0:
                raw_bytes = response.generated_images[0].image.image_bytes

                # Resize / fit to exact requested panel dimensions if aspect ratio differs slightly
                img = Image.open(io.BytesIO(raw_bytes))
                if img.size != (width, height):
                    img = img.resize((width, height), Image.Resampling.LANCZOS)
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()

            raise ValueError("No images returned from Gemini/Imagen API response.")

        except Exception as e:
            logger.error(f"Gemini/Imagen generation failed: {e}. Falling back to REST call.")
            # Fallback to direct HTTP request in case the SDK version differs
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
                    import base64
                    data = res.json()
                    b64_str = data["predictions"][0]["bytesBase64Encoded"]
                    raw_bytes = base64.b64decode(b64_str)
                    img = Image.open(io.BytesIO(raw_bytes))
                    if img.size != (width, height):
                        img = img.resize((width, height), Image.Resampling.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="PNG")
                    return buf.getvalue()
                else:
                    raise ValueError(f"HTTP error {res.status_code}: {res.text}")
            except Exception as http_err:
                raise RuntimeError(
                    f"Gemini Imagen image generation failed with error: {e} | HTTP error: {http_err}"
                ) from e

