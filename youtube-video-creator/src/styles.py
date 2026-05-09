"""Animation styles, video themes, and visual configuration."""

from dataclasses import dataclass
from typing import Optional
import random

# ─── Animation styles ────────────────────────────────────────────────────────

ANIMATION_STYLES = {
    "zoom_in": {
        "label": "Zoom In",
        "description": "Slowly zooms into the image over the duration",
        "zoom_start": 1.0,
        "zoom_end": 1.25,
        "pan_x": 0.0,
        "pan_y": 0.0,
    },
    "zoom_out": {
        "label": "Zoom Out",
        "description": "Starts zoomed in and slowly pulls back",
        "zoom_start": 1.25,
        "zoom_end": 1.0,
        "pan_x": 0.0,
        "pan_y": 0.0,
    },
    "pan_left": {
        "label": "Pan Left",
        "description": "Slowly pans the image from right to left",
        "zoom_start": 1.2,
        "zoom_end": 1.2,
        "pan_x": -0.1,  # fraction of image width per second
        "pan_y": 0.0,
    },
    "pan_right": {
        "label": "Pan Right",
        "description": "Slowly pans the image from left to right",
        "zoom_start": 1.2,
        "zoom_end": 1.2,
        "pan_x": 0.1,
        "pan_y": 0.0,
    },
    "pan_up": {
        "label": "Pan Up",
        "description": "Slowly pans the image upward",
        "zoom_start": 1.2,
        "zoom_end": 1.2,
        "pan_x": 0.0,
        "pan_y": -0.1,
    },
    "pan_down": {
        "label": "Pan Down",
        "description": "Slowly pans the image downward",
        "zoom_start": 1.2,
        "zoom_end": 1.2,
        "pan_x": 0.0,
        "pan_y": 0.1,
    },
    "ken_burns": {
        "label": "Ken Burns",
        "description": "Classic Ken Burns effect with diagonal zoom-pan",
        "zoom_start": 1.0,
        "zoom_end": 1.3,
        "pan_x": 0.05,
        "pan_y": 0.05,
    },
    "static": {
        "label": "Static",
        "description": "No animation, clean static image",
        "zoom_start": 1.0,
        "zoom_end": 1.0,
        "pan_x": 0.0,
        "pan_y": 0.0,
    },
    "random": {
        "label": "Random Mix",
        "description": "Randomly mixes different animation styles per segment",
        "zoom_start": 1.0,
        "zoom_end": 1.2,
        "pan_x": 0.0,
        "pan_y": 0.0,
    },
}

# Styles that can be picked when "random" is selected
RANDOM_POOL = ["zoom_in", "zoom_out", "pan_left", "pan_right", "ken_burns", "pan_up"]


def get_animation_params(style_key: str, index: int = 0) -> dict:
    """Return animation parameters for a given style key."""
    if style_key == "random":
        chosen = RANDOM_POOL[index % len(RANDOM_POOL)]
        return ANIMATION_STYLES[chosen]
    return ANIMATION_STYLES.get(style_key, ANIMATION_STYLES["zoom_in"])


# ─── Transition styles ────────────────────────────────────────────────────────

TRANSITION_STYLES = {
    "fade": "Fade",
    "none": "Cut (No Transition)",
}

# ─── Video themes ─────────────────────────────────────────────────────────────

VIDEO_THEMES = {
    "cinematic": {
        "label": "Cinematic",
        "description": "Dark, dramatic, film-like visuals",
        "image_style": "cinematic photography, dramatic lighting, film grain, wide shot, high contrast, dark moody atmosphere",
        "script_tone": "dramatic, engaging, storytelling",
        "overlay_color": (0, 0, 0, 60),  # RGBA
    },
    "educational": {
        "label": "Educational",
        "description": "Clean, bright, informative visuals",
        "image_style": "clean educational illustration, bright colors, clear and informative, modern flat design",
        "script_tone": "informative, clear, engaging, educational",
        "overlay_color": (0, 30, 60, 40),
    },
    "documentary": {
        "label": "Documentary",
        "description": "Realistic, grounded, journalistic style",
        "image_style": "documentary photography, realistic, natural lighting, journalistic style, high detail",
        "script_tone": "factual, thoughtful, journalistic, compelling",
        "overlay_color": (20, 20, 20, 50),
    },
    "corporate": {
        "label": "Corporate / Business",
        "description": "Professional, clean, modern business visuals",
        "image_style": "professional corporate photography, clean modern office setting, business lifestyle, bright and polished",
        "script_tone": "professional, confident, authoritative",
        "overlay_color": (0, 40, 80, 40),
    },
    "travel": {
        "label": "Travel & Adventure",
        "description": "Vivid, inspiring, wanderlust visuals",
        "image_style": "stunning travel photography, vivid colors, golden hour lighting, breathtaking landscapes, wanderlust",
        "script_tone": "inspiring, adventurous, vivid, descriptive",
        "overlay_color": (10, 30, 10, 30),
    },
    "tech": {
        "label": "Technology",
        "description": "Futuristic, digital, innovative visuals",
        "image_style": "futuristic technology visualization, digital art, blue neon accents, sleek and modern, cyberpunk aesthetic",
        "script_tone": "innovative, forward-thinking, technical yet accessible",
        "overlay_color": (0, 10, 40, 50),
    },
    "lifestyle": {
        "label": "Lifestyle",
        "description": "Warm, relatable, everyday life visuals",
        "image_style": "lifestyle photography, warm tones, natural light, relatable everyday moments, candid feel",
        "script_tone": "warm, relatable, conversational, inspiring",
        "overlay_color": (30, 15, 0, 30),
    },
    "nature": {
        "label": "Nature & Wildlife",
        "description": "Lush, vibrant, natural world visuals",
        "image_style": "nature photography, lush landscapes, wildlife, macro details, golden hour, National Geographic style",
        "script_tone": "awe-inspiring, descriptive, educational",
        "overlay_color": (0, 20, 0, 30),
    },
}

# ─── Voice configurations ─────────────────────────────────────────────────────

ELEVENLABS_VOICES = {
    "Rachel": {
        "id": "21m00Tcm4TlvDq8ikWAM",
        "description": "Calm, professional female voice",
        "gender": "Female",
    },
    "Domi": {
        "id": "AZnzlk1XvdvUeBnXmlld",
        "description": "Strong, confident female voice",
        "gender": "Female",
    },
    "Bella": {
        "id": "EXAVITQu4vr4xnSDxMaL",
        "description": "Soft, warm female voice",
        "gender": "Female",
    },
    "Antoni": {
        "id": "ErXwobaYiN019PkySvjV",
        "description": "Deep, resonant male voice",
        "gender": "Male",
    },
    "Elli": {
        "id": "MF3mGyEYCl7XYWbV9V6O",
        "description": "Energetic, young female voice",
        "gender": "Female",
    },
    "Josh": {
        "id": "TxGEqnHWrfWFTfGW9XjX",
        "description": "Warm, authoritative male voice",
        "gender": "Male",
    },
    "Arnold": {
        "id": "VR6AewLTigWG4xSOukaG",
        "description": "Bold, dramatic male voice",
        "gender": "Male",
    },
    "Adam": {
        "id": "pNInz6obpgDQGcFmaJgB",
        "description": "Professional, clear male voice",
        "gender": "Male",
    },
    "Sam": {
        "id": "yoZ06aMxZJJ28mfd3POQ",
        "description": "Friendly, conversational male voice",
        "gender": "Male",
    },
}

# ─── Video length presets ─────────────────────────────────────────────────────

VIDEO_LENGTH_PRESETS = {
    "30 seconds": 30,
    "1 minute": 60,
    "2 minutes": 120,
    "3 minutes": 180,
    "5 minutes": 300,
    "10 minutes": 600,
    "Custom": -1,
}

# ─── Resolution presets ───────────────────────────────────────────────────────

RESOLUTIONS = {
    "1080p (1920×1080)": (1920, 1080),
    "720p (1280×720)": (1280, 720),
    "4K (3840×2160)": (3840, 2160),
    "Square (1080×1080)": (1080, 1080),
    "Vertical / Shorts (1080×1920)": (1080, 1920),
}
