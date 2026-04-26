"""Unified image generation service — multi-provider with cost tiers.

Providers:
  - Flux Pro 1.1 (BFL): best quality, $0.055/image
  - GPT Image (OpenAI): controllable, $0.04/image
  - Ideogram v3: best text-in-image, $0.03-0.05/image
  - Flux Schnell (BFL): fast/cheap drafts, $0.015/image

Usage:
    result = await image_generator.generate(
        prompt="A woman looking at her phone at 11pm...",
        provider="flux_pro",
        aspect_ratio="4:5",
    )
    # result.image_url → presigned URL to generated image
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class ImageProvider(str, Enum):
    FLUX_PRO = "flux_pro"
    FLUX_SCHNELL = "flux_schnell"
    GPT_IMAGE = "gpt_image"
    IDEOGRAM = "ideogram"


PROVIDER_COSTS: dict[ImageProvider, float] = {
    ImageProvider.FLUX_PRO: 0.055,
    ImageProvider.FLUX_SCHNELL: 0.015,
    ImageProvider.GPT_IMAGE: 0.04,
    ImageProvider.IDEOGRAM: 0.04,
}


@dataclass
class ImageResult:
    provider: str
    prompt: str
    image_url: str | None = None
    image_bytes: bytes | None = None
    width: int = 0
    height: int = 0
    cost: float = 0.0
    metadata: dict[str, Any] | None = None
    error: str | None = None


class ImageGenerator:
    """Multi-provider image generation with automatic fallback."""

    async def generate(
        self,
        prompt: str,
        *,
        provider: ImageProvider | str = ImageProvider.FLUX_PRO,
        aspect_ratio: str = "1:1",
        negative_prompt: str | None = None,
        style: str | None = None,
        num_images: int = 1,
    ) -> list[ImageResult]:
        """Generate images from a prompt.

        Args:
            prompt: The image generation prompt.
            provider: Which API to use.
            aspect_ratio: 1:1, 4:5, 9:16, 16:9.
            negative_prompt: What to avoid in the image.
            style: Style modifier (e.g., "photo", "illustration").
            num_images: How many variants to generate.
        """
        if isinstance(provider, str):
            provider = ImageProvider(provider)

        results: list[ImageResult] = []

        for _ in range(num_images):
            try:
                if provider == ImageProvider.FLUX_PRO:
                    result = await self._generate_flux(
                        prompt, "flux-pro-1.1", aspect_ratio, negative_prompt,
                    )
                elif provider == ImageProvider.FLUX_SCHNELL:
                    result = await self._generate_flux(
                        prompt, "flux-schnell", aspect_ratio, negative_prompt,
                    )
                elif provider == ImageProvider.GPT_IMAGE:
                    result = await self._generate_gpt_image(
                        prompt, aspect_ratio, style,
                    )
                elif provider == ImageProvider.IDEOGRAM:
                    result = await self._generate_ideogram(
                        prompt, aspect_ratio, negative_prompt, style,
                    )
                else:
                    result = ImageResult(
                        provider=provider.value,
                        prompt=prompt,
                        error=f"Unknown provider: {provider}",
                    )

                result.cost = PROVIDER_COSTS.get(provider, 0.0)
                results.append(result)

            except Exception as exc:
                logger.warning(
                    "image_gen.failed provider=%s error=%s",
                    provider.value, exc,
                )
                results.append(ImageResult(
                    provider=provider.value,
                    prompt=prompt,
                    error=str(exc),
                ))

        return results

    async def generate_batch(
        self,
        prompts: list[dict[str, Any]],
        *,
        default_provider: ImageProvider = ImageProvider.FLUX_PRO,
    ) -> list[ImageResult]:
        """Generate images for multiple prompts.

        Each prompt dict can override provider, aspect_ratio, etc.
        """
        results: list[ImageResult] = []
        for p in prompts:
            batch = await self.generate(
                prompt=p.get("prompt", ""),
                provider=p.get("provider", default_provider),
                aspect_ratio=p.get("aspect_ratio", "1:1"),
                negative_prompt=p.get("negative_prompt"),
                style=p.get("style"),
            )
            results.extend(batch)
        return results

    async def _generate_flux(
        self,
        prompt: str,
        model: str,
        aspect_ratio: str,
        negative_prompt: str | None,
    ) -> ImageResult:
        """Generate via BFL Flux API (flux-pro-1.1 or flux-schnell)."""
        width, height = _parse_aspect_ratio(aspect_ratio)

        async with httpx.AsyncClient(timeout=120) as client:
            # Submit generation request
            payload: dict[str, Any] = {
                "prompt": prompt,
                "width": width,
                "height": height,
            }
            if negative_prompt:
                payload["negative_prompt"] = negative_prompt

            resp = await client.post(
                f"https://api.bfl.ml/v1/{model}",
                json=payload,
                headers={"X-Key": settings.BFL_API_KEY},
            )
            resp.raise_for_status()
            data = resp.json()

            task_id = data.get("id")
            if not task_id:
                return ImageResult(
                    provider=model, prompt=prompt,
                    error="No task ID returned",
                )

            # Poll for result
            for _ in range(60):
                import asyncio
                await asyncio.sleep(2)
                poll = await client.get(
                    f"https://api.bfl.ml/v1/get_result?id={task_id}",
                    headers={"X-Key": settings.BFL_API_KEY},
                )
                poll_data = poll.json()
                status = poll_data.get("status")

                if status == "Ready":
                    image_url = poll_data.get("result", {}).get("sample")
                    return ImageResult(
                        provider=model, prompt=prompt,
                        image_url=image_url,
                        width=width, height=height,
                    )
                elif status in ("Error", "Failed"):
                    return ImageResult(
                        provider=model, prompt=prompt,
                        error=poll_data.get("result", "Generation failed"),
                    )

            return ImageResult(
                provider=model, prompt=prompt, error="Generation timed out",
            )

    async def _generate_gpt_image(
        self,
        prompt: str,
        aspect_ratio: str,
        style: str | None,
    ) -> ImageResult:
        """Generate via OpenAI Images API (GPT-Image / DALL-E)."""
        if not settings.OPENAI_API_KEY:
            return ImageResult(
                provider="gpt_image", prompt=prompt,
                error="OPENAI_API_KEY not configured",
            )

        try:
            import openai
            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            size_map = {
                "1:1": "1024x1024",
                "4:5": "1024x1280",
                "9:16": "768x1344",
                "16:9": "1536x1024",
            }
            size = size_map.get(aspect_ratio, "1024x1024")

            response = await client.images.generate(
                model="gpt-image-1",
                prompt=prompt,
                size=size,
                n=1,
                quality="high",
                style=style or "natural",
            )

            image_data = response.data[0]
            w, h = (int(x) for x in size.split("x"))

            return ImageResult(
                provider="gpt_image", prompt=prompt,
                image_url=getattr(image_data, "url", None),
                width=w, height=h,
            )
        except ImportError:
            return ImageResult(
                provider="gpt_image", prompt=prompt,
                error="openai package not installed",
            )

    async def _generate_ideogram(
        self,
        prompt: str,
        aspect_ratio: str,
        negative_prompt: str | None,
        style: str | None,
    ) -> ImageResult:
        """Generate via Ideogram API (best for text-in-image)."""
        ideogram_key = getattr(settings, "IDEOGRAM_API_KEY", "")
        if not ideogram_key:
            return ImageResult(
                provider="ideogram", prompt=prompt,
                error="IDEOGRAM_API_KEY not configured",
            )

        async with httpx.AsyncClient(timeout=60) as client:
            payload: dict[str, Any] = {
                "image_request": {
                    "prompt": prompt,
                    "aspect_ratio": aspect_ratio.replace(":", "_"),
                    "model": "V_3",
                },
            }
            if negative_prompt:
                payload["image_request"]["negative_prompt"] = negative_prompt
            if style:
                payload["image_request"]["style_type"] = style.upper()

            resp = await client.post(
                "https://api.ideogram.ai/generate",
                json=payload,
                headers={"Api-Key": ideogram_key},
            )
            resp.raise_for_status()
            data = resp.json()

            images = data.get("data", [])
            if images:
                return ImageResult(
                    provider="ideogram", prompt=prompt,
                    image_url=images[0].get("url"),
                    width=images[0].get("resolution", {}).get("width", 0),
                    height=images[0].get("resolution", {}).get("height", 0),
                )

            return ImageResult(
                provider="ideogram", prompt=prompt,
                error="No images returned",
            )


def _parse_aspect_ratio(ratio: str) -> tuple[int, int]:
    """Convert aspect ratio string to pixel dimensions."""
    ratios = {
        "1:1": (1024, 1024),
        "4:5": (1024, 1280),
        "5:4": (1280, 1024),
        "9:16": (768, 1344),
        "16:9": (1344, 768),
    }
    return ratios.get(ratio, (1024, 1024))


image_generator = ImageGenerator()
