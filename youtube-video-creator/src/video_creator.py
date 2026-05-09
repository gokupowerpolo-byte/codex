"""
Video creator: assembles animated image clips + audio into a final MP4.
Uses MoviePy with custom Ken Burns / pan / zoom frame generators.
"""

import os
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from moviepy.editor import (
    VideoClip,
    AudioFileClip,
    concatenate_videoclips,
    CompositeVideoClip,
    ImageClip,
    ColorClip,
)
from .styles import get_animation_params, ANIMATION_STYLES


# ─── Frame generators for animated clips ──────────────────────────────────────

def _make_animated_frame_fn(img_array: np.ndarray, duration: float, params: dict, out_w: int, out_h: int):
    """
    Return a function t -> np.ndarray that applies the animation parameters
    to produce a video frame at time t.

    Works by maintaining an oversized work canvas (130% of output) and
    sampling a moving/zooming crop window from it.
    """
    h, w = img_array.shape[:2]

    def make_frame(t: float) -> np.ndarray:
        progress = t / duration if duration > 0 else 0.0

        zoom_start = params["zoom_start"]
        zoom_end = params["zoom_end"]
        zoom = zoom_start + (zoom_end - zoom_start) * progress

        # Base crop size at current zoom (before panning)
        crop_w = int(out_w / zoom)
        crop_h = int(out_h / zoom)

        # Clamp crop to image bounds
        crop_w = min(crop_w, w)
        crop_h = min(crop_h, h)

        # Center offset for zoom
        cx = (w - crop_w) // 2
        cy = (h - crop_h) // 2

        # Apply pan (fraction of image size per unit time, scaled by progress)
        pan_x_px = int(params["pan_x"] * w * progress)
        pan_y_px = int(params["pan_y"] * h * progress)

        x0 = np.clip(cx + pan_x_px, 0, w - crop_w)
        y0 = np.clip(cy + pan_y_px, 0, h - crop_h)
        x1 = x0 + crop_w
        y1 = y0 + crop_h

        cropped = img_array[y0:y1, x0:x1]

        # Resize to exact output resolution
        pil = Image.fromarray(cropped).resize((out_w, out_h), Image.LANCZOS)
        return np.array(pil)

    return make_frame


def create_animated_clip(
    image_path: str,
    duration: float,
    animation_style: str,
    style_index: int,
    out_w: int,
    out_h: int,
    fps: int = 24,
) -> VideoClip:
    """Build a VideoClip with the chosen animation applied to the given image."""
    params = get_animation_params(animation_style, style_index)

    # Load image and scale up so there is room to zoom/pan without black bars.
    # The oversample factor must be >= max(zoom_start, zoom_end) so we never
    # run out of source pixels to crop from.
    oversample = max(params["zoom_start"], params["zoom_end"]) * 1.05
    work_w = int(out_w * oversample)
    work_h = int(out_h * oversample)

    img = Image.open(image_path).convert("RGB").resize((work_w, work_h), Image.LANCZOS)
    img_array = np.array(img)

    frame_fn = _make_animated_frame_fn(img_array, duration, params, out_w, out_h)
    clip = VideoClip(frame_fn, duration=duration).set_fps(fps)
    return clip


# ─── Caption overlay ─────────────────────────────────────────────────────────

def _make_caption_clip(
    text: str,
    out_w: int,
    out_h: int,
    duration: float,
    fps: int = 24,
    fade_duration: float = 0.5,
) -> ImageClip:
    """Render a semi-transparent caption bar at the bottom of the frame."""
    bar_h = max(60, out_h // 12)
    canvas = Image.new("RGBA", (out_w, bar_h), (0, 0, 0, 160))
    draw = ImageDraw.Draw(canvas)

    # Try to load a system font; fall back to PIL default
    font_size = max(24, out_h // 30)
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    x = (out_w - text_w) // 2
    y = (bar_h - text_h) // 2
    draw.text((x, y), text, fill=(255, 255, 255, 255), font=font)

    bar_array = np.array(canvas.convert("RGB"))

    # Place at bottom of frame
    y_position = out_h - bar_h - 20

    caption_clip = (
        ImageClip(bar_array)
        .set_duration(duration)
        .set_position(("center", y_position))
        .set_fps(fps)
        .crossfadein(fade_duration)
        .crossfadeout(fade_duration)
    )
    return caption_clip


# ─── Segment assembly ────────────────────────────────────────────────────────

def build_segment_clip(
    segment: dict,
    animation_style: str,
    out_w: int,
    out_h: int,
    fps: int,
    show_captions: bool,
) -> VideoClip:
    """Assemble a single segment: animated image + audio + optional caption."""
    image_path = segment["image_path"]
    audio_path = segment.get("audio_path")

    # Prefer actual recorded audio duration; fall back to script estimate
    duration = segment.get("actual_duration", segment.get("estimated_duration", 5.0))
    # Ensure minimum clip length
    duration = max(duration, 2.0)

    idx = segment["index"]
    video_clip = create_animated_clip(
        image_path=image_path,
        duration=duration,
        animation_style=animation_style,
        style_index=idx,
        out_w=out_w,
        out_h=out_h,
        fps=fps,
    )

    if audio_path and os.path.exists(audio_path):
        audio = AudioFileClip(audio_path)
        # Trim audio if it's slightly longer than image clip duration
        if audio.duration > duration:
            audio = audio.subclip(0, duration)
        video_clip = video_clip.set_audio(audio)

    # Caption overlay
    caption_text = segment.get("caption", "").strip()
    if show_captions and caption_text:
        caption = _make_caption_clip(caption_text, out_w, out_h, duration, fps)
        video_clip = CompositeVideoClip([video_clip, caption])

    return video_clip


# ─── Full video assembly ──────────────────────────────────────────────────────

def create_video(
    segments: list,
    output_path: str,
    animation_style: str = "zoom_in",
    transition_style: str = "fade",
    resolution: tuple = (1920, 1080),
    fps: int = 24,
    show_captions: bool = True,
    progress_callback=None,
) -> str:
    """
    Build the final video from all segments.

    Args:
        segments: list of dicts with image_path, audio_path, actual_duration, etc.
        output_path: where to write the final .mp4
        animation_style: key from ANIMATION_STYLES
        transition_style: "fade" or "none"
        resolution: (width, height) tuple
        fps: frames per second
        show_captions: whether to overlay caption text
        progress_callback: callable(step, total_steps)

    Returns the output file path.
    """
    out_w, out_h = resolution
    total_steps = len(segments) + 2  # build clips + concat + encode
    step = 0

    # Build individual clips
    clips = []
    for seg in segments:
        clip = build_segment_clip(
            segment=seg,
            animation_style=animation_style,
            out_w=out_w,
            out_h=out_h,
            fps=fps,
            show_captions=show_captions,
        )

        if transition_style == "fade" and len(clips) > 0:
            fade_dur = min(0.5, clip.duration / 4)
            clip = clip.crossfadein(fade_dur)

        clips.append(clip)
        step += 1
        if progress_callback:
            progress_callback(step, total_steps)

    if not clips:
        raise ValueError("No clips to assemble — segments list is empty")

    # Concatenate all segments
    method = "compose" if transition_style == "fade" else "chain"
    final = concatenate_videoclips(clips, method=method)

    step += 1
    if progress_callback:
        progress_callback(step, total_steps)

    # Write to disk
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    final.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        preset="fast",
        ffmpeg_params=["-crf", "23"],
        logger=None,  # suppress verbose moviepy logs
    )

    step += 1
    if progress_callback:
        progress_callback(step, total_steps)

    # Clean up clip handles to release file locks
    for c in clips:
        try:
            c.close()
        except Exception:
            pass
    final.close()

    return output_path
