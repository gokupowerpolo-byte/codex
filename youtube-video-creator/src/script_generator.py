"""Gemini-powered script generator that produces structured, timed video scripts."""

import json
import re
from typing import Optional
from google import genai
from google.genai import types


def _build_prompt(
    topic: str,
    theme_label: str,
    theme_tone: str,
    theme_image_style: str,
    target_length_seconds: int,
    image_count: Optional[int],
    target_audience: str,
) -> str:
    # Estimate word count: ~150 words per minute of narration
    target_words = int((target_length_seconds / 60) * 150)
    auto_images = image_count or max(3, target_length_seconds // 5)

    return f"""You are a professional YouTube video scriptwriter. Create a complete, engaging script for a {theme_label}-style video.

TOPIC: {topic}
TARGET AUDIENCE: {target_audience}
TOTAL VIDEO LENGTH: {target_length_seconds} seconds (~{target_words} words of narration)
NUMBER OF VISUAL SEGMENTS: {auto_images}
SCRIPT TONE: {theme_tone}

Your task:
1. Write a compelling, natural-sounding narration script split into exactly {auto_images} segments
2. Each segment must have a vivid, specific image description that visually matches the narration
3. Distribute narration evenly so segments add up to approximately {target_length_seconds} seconds total
4. Image descriptions should use this visual style: {theme_image_style}

Return ONLY valid JSON in this exact structure (no markdown, no explanation):
{{
  "title": "Compelling YouTube video title",
  "description": "SEO-optimized YouTube description (2-3 sentences)",
  "tags": ["tag1", "tag2", "tag3", "tag4", "tag5"],
  "total_estimated_duration": {target_length_seconds},
  "segments": [
    {{
      "index": 0,
      "narration": "Exact words to be spoken by the narrator. This should be natural, engaging prose.",
      "scene_description": "Highly detailed image generation prompt. Describe exactly what should be shown visually. Include composition, lighting, colors, mood, and subject. Style: {theme_image_style}.",
      "estimated_duration": 5.0,
      "caption": "Short on-screen text (optional, max 6 words)"
    }}
  ]
}}

Rules:
- narration must sound natural when spoken aloud — no bullet points, no headers
- scene_description must be a complete standalone image prompt with the visual style embedded
- estimated_duration is in seconds; the sum of all segments should equal {target_length_seconds}
- captions are optional short titles that could appear on screen
- Make the opening segment hook the viewer immediately
- Make the final segment have a strong call-to-action
"""


def generate_script(
    google_api_key: str,
    topic: str,
    theme: dict,
    target_length_seconds: int,
    image_count: Optional[int],
    target_audience: str = "general audience",
) -> dict:
    """
    Generate a structured video script using Gemini.

    Returns a dict with keys: title, description, tags, total_estimated_duration, segments.
    Each segment has: index, narration, scene_description, estimated_duration, caption.
    """
    client = genai.Client(api_key=google_api_key)

    prompt = _build_prompt(
        topic=topic,
        theme_label=theme["label"],
        theme_tone=theme["script_tone"],
        theme_image_style=theme["image_style"],
        target_length_seconds=target_length_seconds,
        image_count=image_count,
        target_audience=target_audience,
    )

    response = client.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            temperature=0.8,
            max_output_tokens=8192,
        ),
    )

    raw = response.text.strip()

    # Strip markdown code fences if Gemini wraps in ```json ... ```
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\n?", "", raw)
        raw = re.sub(r"\n?```$", "", raw)

    script = json.loads(raw)

    # Normalize segment indexes in case Gemini mis-numbered them
    for i, seg in enumerate(script.get("segments", [])):
        seg["index"] = i

    return script


def auto_calculate_image_count(
    target_length_seconds: int,
    min_segment_duration: float = 4.0,
    max_segment_duration: float = 8.0,
) -> int:
    """
    Calculate the ideal number of images so each image lasts between
    min_segment_duration and max_segment_duration seconds.
    """
    ideal = target_length_seconds / ((min_segment_duration + max_segment_duration) / 2)
    return max(3, min(30, round(ideal)))


def redistribute_durations(segments: list, total_seconds: int) -> list:
    """
    After real audio durations are known, rebalance segment durations
    proportionally so they still add up to the target total.
    Segments without audio yet keep their estimated_duration.
    """
    current_total = sum(s.get("actual_duration", s["estimated_duration"]) for s in segments)
    if current_total == 0:
        return segments

    scale = total_seconds / current_total
    for seg in segments:
        base = seg.get("actual_duration", seg["estimated_duration"])
        seg["video_duration"] = max(2.0, base * scale)

    return segments
