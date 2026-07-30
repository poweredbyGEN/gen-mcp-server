"""Canonical generation-type -> Rails internal type mapping.

Faithful port of SIMPLE_TYPE_MAP / MODEL_ROUTED_TYPE_MAP / resolveGenerationType
from the TS server (src/index.ts). Keep in lockstep with the backend.
"""

from __future__ import annotations

SIMPLE_TYPE_MAP: dict[str, str] = {
    "text": "text_generation",
    "speech_from_text": "eleven_labs",
}


def _image_from_text(model: str) -> str:
    if model == "midjourney":
        return "midjourney"
    if model == "grok":
        return "grok_image_generation"
    return "gemini_image_generation"


def _video_from_text(model: str) -> str:
    if model.startswith("sora"):
        return "sora2_video_generation"
    if model.startswith("kling"):
        return "kling"
    if model == "seedance-2.0" or model == "seedance_2_0":
        return "seedance_2_0_video_generation"
    if model.startswith("seedance"):
        return "seedance_video_generation"
    if model == "grok":
        return "grok_video_generation"
    return "gemini_video_generation"


def _video_from_image(model: str) -> str:
    if model.startswith("kling"):
        return "kling_image_video"
    if model.startswith("sora"):
        return "sora2_video_generation"
    if model == "seedance-2.0" or model == "seedance_2_0":
        return "seedance_2_0_video_generation"
    if model.startswith("seedance"):
        return "seedance_video_generation"
    if model == "grok":
        return "grok_video_generation"
    return "gemini_video_generation"


MODEL_ROUTED_TYPE_MAP = {
    "image_from_text": _image_from_text,
    "video_from_text": _video_from_text,
    "video_from_image": _video_from_image,
}


def resolve_generation_type(canonical_type: str, data: dict | None = None) -> str:
    if canonical_type in SIMPLE_TYPE_MAP:
        return SIMPLE_TYPE_MAP[canonical_type]
    router = MODEL_ROUTED_TYPE_MAP.get(canonical_type)
    if router:
        model = str((data or {}).get("model") or "")
        return router(model)
    # Already a Rails type or unknown — pass through unchanged.
    return canonical_type
