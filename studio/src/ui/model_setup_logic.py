"""Pure logic behind the first-run model setup window (no Qt, so it is easy to test).

There is no default provider: the person picks one of the cloud providers and pastes their own key.
"""
from typing import Any, Dict, Optional

from src.providers.provider_factory import CLOUD_IMAGE_PROVIDERS, CLOUD_PROVIDERS

LABELS = {"anthropic": "Anthropic", "gemini": "Google Gemini", "openai": "OpenAI"}
SAME = "same"   # image slot uses the same provider as text/vision


def image_choices(main: Optional[str]):
    """Which image sources can be offered for a given main provider."""
    out = []
    if main in CLOUD_IMAGE_PROVIDERS:
        out.append(SAME)
    out.extend(CLOUD_IMAGE_PROVIDERS)
    return out


def is_complete(main: Optional[str], key: str, image: Optional[str], image_key: str) -> bool:
    """True when the window has everything needed to save."""
    if main not in CLOUD_PROVIDERS or not key.strip():
        return False
    if image == SAME:
        return main in CLOUD_IMAGE_PROVIDERS
    if image not in CLOUD_IMAGE_PROVIDERS:
        return False
    return image == main or bool(image_key.strip())


def build_config(config: Optional[Dict[str, Any]], main: str, key: str, image: str, image_key: str = "") -> Dict[str, Any]:
    """Return a copy of config with the chosen providers and keys. Other providers' saved keys are kept."""
    cfg = dict(config or {})
    if image == SAME:
        image = main
    cfg["text_provider"] = main
    cfg["vision_provider"] = main
    cfg["image_provider"] = image
    cfg[f"{main}_api_key"] = key.strip()
    if image != main:
        # a different company for images: its key goes in the image-specific field
        cfg["image_api_key" if image == "gemini" else f"image_{image}_api_key"] = image_key.strip()
    else:
        cfg["image_api_key" if image == "gemini" else f"image_{image}_api_key"] = ""
    return cfg
