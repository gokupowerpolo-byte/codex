"""Gemini Imagen-powered image generator for video segments."""

import io
import os
import time
from pathlib import Path
from typing import Optional
from PIL import Image
from google import genai
from google.genai import types


def generate_image(
    google_api_key: str,
    prompt: str,
    output_path: str,
    aspect_ratio: str = "16:9",
    retries: int = 3,
) -> str:
    """
    Generate an image using Google Imagen and save to output_path.
    Returns the saved file path.

    aspect_ratio options: "1:1", "3:4", "4:3", "9:16", "16:9"
    """
    client = genai.Client(api_key=google_api_key)

    last_error = None
    for attempt in range(retries):
        try:
            response = client.models.generate_images(
                model="imagen-3.0-generate-002",
                prompt=prompt,
                config=types.GenerateImagesConfig(
                    number_of_images=1,
                    aspect_ratio=aspect_ratio,
                    safety_filter_level="block_only_high",
                    person_generation="allow_adult",
                ),
            )

            if not response.generated_images:
                raise ValueError("No images returned from Imagen API")

            image_bytes = response.generated_images[0].image.image_bytes
            img = Image.open(io.BytesIO(image_bytes)).convert("RGB")

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            img.save(output_path, "JPEG", quality=95)
            return output_path

        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                # Exponential backoff between retries
                time.sleep(2 ** attempt)
            continue

    raise RuntimeError(f"Image generation failed after {retries} attempts: {last_error}")


def get_aspect_ratio_for_resolution(width: int, height: int) -> str:
    """Map a resolution to the closest supported Imagen aspect ratio."""
    ratio = width / height
    candidates = {
        "1:1": 1.0,
        "4:3": 4 / 3,
        "3:4": 3 / 4,
        "16:9": 16 / 9,
        "9:16": 9 / 16,
    }
    return min(candidates, key=lambda k: abs(candidates[k] - ratio))


def resize_image_to_resolution(image_path: str, width: int, height: int) -> str:
    """
    Resize and center-crop an image to exactly (width, height).
    Overwrites the file in place. Returns the path.
    """
    img = Image.open(image_path).convert("RGB")

    # Scale so the image covers the target while preserving aspect ratio
    img_ratio = img.width / img.height
    target_ratio = width / height

    if img_ratio > target_ratio:
        # Image is wider than target — scale by height
        scale_h = height
        scale_w = int(img.width * height / img.height)
    else:
        # Image is taller than target — scale by width
        scale_w = width
        scale_h = int(img.height * width / img.width)

    img = img.resize((scale_w, scale_h), Image.LANCZOS)

    # Center crop to exact target
    x_start = (scale_w - width) // 2
    y_start = (scale_h - height) // 2
    img = img.crop((x_start, y_start, x_start + width, y_start + height))

    img.save(image_path, "JPEG", quality=95)
    return image_path


def generate_all_images(
    google_api_key: str,
    segments: list,
    output_dir: str,
    width: int,
    height: int,
    progress_callback=None,
) -> list:
    """
    Generate images for all segments. Returns segments with 'image_path' populated.
    progress_callback(segment_index, total) is called after each image completes.
    """
    aspect_ratio = get_aspect_ratio_for_resolution(width, height)
    total = len(segments)

    for seg in segments:
        idx = seg["index"]
        output_path = os.path.join(output_dir, f"image_{idx:03d}.jpg")

        if os.path.exists(output_path):
            seg["image_path"] = output_path
            if progress_callback:
                progress_callback(idx, total)
            continue

        generate_image(
            google_api_key=google_api_key,
            prompt=seg["scene_description"],
            output_path=output_path,
            aspect_ratio=aspect_ratio,
        )

        # Ensure exact pixel dimensions for video consistency
        resize_image_to_resolution(output_path, width, height)
        seg["image_path"] = output_path

        if progress_callback:
            progress_callback(idx, total)

    return segments
