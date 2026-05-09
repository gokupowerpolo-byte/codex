"""
YouTube AI Video Creator
────────────────────────
Generates complete YouTube videos from a topic using:
  • Google Gemini (script + image generation via Imagen 3)
  • ElevenLabs (free-tier TTS narration)
  • MoviePy (animated image-to-video assembly)
"""

import os
import json
import time
import shutil
import tempfile
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

from src.styles import (
    ANIMATION_STYLES,
    TRANSITION_STYLES,
    VIDEO_THEMES,
    VIDEO_LENGTH_PRESETS,
    RESOLUTIONS,
    ELEVENLABS_VOICES,
)
from src.script_generator import (
    generate_script,
    auto_calculate_image_count,
    redistribute_durations,
)
from src.image_generator import generate_all_images
from src.voice_generator import generate_all_voices
from src.video_creator import create_video

load_dotenv()

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="YouTube AI Video Creator",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Custom CSS ───────────────────────────────────────────────────────────────

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.5rem;
        font-weight: 800;
        background: linear-gradient(135deg, #FF0000, #FF6B35, #FFD700);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .subtitle {
        color: #888;
        font-size: 1rem;
        margin-bottom: 2rem;
    }
    .segment-card {
        background: #1a1a2e;
        border: 1px solid #333;
        border-radius: 10px;
        padding: 1rem;
        margin-bottom: 0.8rem;
    }
    .segment-index {
        color: #FF6B35;
        font-weight: bold;
        font-size: 0.85rem;
    }
    .narration-text {
        color: #e0e0e0;
        font-size: 0.95rem;
        line-height: 1.5;
    }
    .scene-text {
        color: #aaa;
        font-size: 0.8rem;
        font-style: italic;
    }
    .stProgress > div > div {
        background: linear-gradient(90deg, #FF0000, #FF6B35);
    }
    div[data-testid="stSidebarContent"] {
        background: #0f0f1a;
    }
    </style>
    """,
    unsafe_allow_html=True,
)

# ─── Session state initialisation ─────────────────────────────────────────────

def _init_state():
    defaults = {
        "script": None,
        "segments": None,
        "output_dir": None,
        "video_path": None,
        "step": "input",  # input → script → generate → done
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_state()

# ─── Sidebar ──────────────────────────────────────────────────────────────────

with st.sidebar:
    st.markdown("## ⚙️ Settings")

    st.markdown("### 🔑 API Keys")
    google_api_key = st.text_input(
        "Google AI API Key",
        value=os.getenv("GOOGLE_API_KEY", ""),
        type="password",
        help="Get yours at https://aistudio.google.com/app/apikey",
    )
    elevenlabs_api_key = st.text_input(
        "ElevenLabs API Key",
        value=os.getenv("ELEVENLABS_API_KEY", ""),
        type="password",
        help="Free key at https://elevenlabs.io — 10,000 chars/month included",
    )

    st.markdown("---")
    st.markdown("### 🎨 Video Style")

    theme_key = st.selectbox(
        "Theme",
        options=list(VIDEO_THEMES.keys()),
        format_func=lambda k: VIDEO_THEMES[k]["label"],
        help="Sets the visual mood, image style, and script tone",
    )
    theme = VIDEO_THEMES[theme_key]
    st.caption(f"_{theme['description']}_")

    st.markdown("---")
    st.markdown("### ⏱️ Video Length")

    length_preset = st.selectbox(
        "Target Duration",
        options=list(VIDEO_LENGTH_PRESETS.keys()),
        index=1,  # default: 1 minute
    )
    if length_preset == "Custom":
        target_length = st.slider("Custom Length (seconds)", 15, 900, 90, step=15)
    else:
        target_length = VIDEO_LENGTH_PRESETS[length_preset]

    st.markdown("---")
    st.markdown("### 🖼️ Images")

    image_mode = st.radio(
        "Image Count",
        ["Auto (based on script)", "Custom"],
        index=0,
    )
    if image_mode == "Custom":
        custom_image_count = st.slider("Number of Images", 3, 30, 8)
    else:
        custom_image_count = None
        auto_count = auto_calculate_image_count(target_length)
        st.info(f"Auto: ~{auto_count} images for {target_length}s video")

    st.markdown("---")
    st.markdown("### 🎬 Animation")

    animation_style = st.selectbox(
        "Animation Style",
        options=list(ANIMATION_STYLES.keys()),
        format_func=lambda k: ANIMATION_STYLES[k]["label"],
        index=0,
    )
    st.caption(f"_{ANIMATION_STYLES[animation_style]['description']}_")

    transition_style = st.selectbox(
        "Transition",
        options=list(TRANSITION_STYLES.keys()),
        format_func=lambda k: TRANSITION_STYLES[k],
    )

    show_captions = st.toggle("Show Captions", value=True)

    st.markdown("---")
    st.markdown("### 🔊 Voice")

    voice_name = st.selectbox(
        "Narrator Voice",
        options=list(ELEVENLABS_VOICES.keys()),
        format_func=lambda k: f"{k} — {ELEVENLABS_VOICES[k]['gender']}",
    )
    voice_info = ELEVENLABS_VOICES[voice_name]
    st.caption(f"_{voice_info['description']}_")

    voice_stability = st.slider("Stability", 0.0, 1.0, 0.50, 0.05)
    voice_similarity = st.slider("Clarity / Similarity", 0.0, 1.0, 0.75, 0.05)

    st.markdown("---")
    st.markdown("### 📐 Resolution")

    resolution_label = st.selectbox(
        "Output Resolution",
        options=list(RESOLUTIONS.keys()),
        index=1,  # default 720p for speed
    )
    resolution = RESOLUTIONS[resolution_label]

    fps = st.select_slider("Frame Rate", options=[24, 30, 60], value=24)

    st.markdown("---")
    st.markdown("### 🎯 Audience")
    target_audience = st.text_input("Target Audience", value="general audience")

# ─── Main area ────────────────────────────────────────────────────────────────

st.markdown('<div class="main-title">YouTube AI Video Creator</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="subtitle">Generate complete YouTube videos from a single topic using Gemini + ElevenLabs</div>',
    unsafe_allow_html=True,
)

# ── Step 1: Topic input ────────────────────────────────────────────────────────

topic = st.text_area(
    "Video Topic",
    placeholder="e.g. '10 Fascinating Facts About the Deep Ocean', 'How Quantum Computing Will Change the World', 'The Rise and Fall of the Roman Empire'",
    height=100,
)

# ── Reference image upload ─────────────────────────────────────────────────────

with st.expander("📷 Upload a Reference Image (optional)", expanded=False):
    st.markdown(
        "Upload an image and Gemini will analyse it to inspire the script topic, "
        "scene descriptions, and visual style. Great for product videos, travel content, "
        "or when you have a specific visual in mind."
    )
    uploaded_image = st.file_uploader(
        "Reference Image",
        type=["jpg", "jpeg", "png", "webp"],
        label_visibility="collapsed",
    )
    if uploaded_image is not None:
        col_img, col_hint = st.columns([1, 2])
        with col_img:
            st.image(uploaded_image, use_container_width=True)
        with col_hint:
            st.success("Image uploaded — Gemini will use this to shape the script.")
            st.caption(
                "The topic field above can be left blank or used to give additional context "
                "(e.g. 'make it funny' or 'focus on the architecture')."
            )

col1, col2, col3 = st.columns([2, 2, 3])
with col1:
    gen_script_btn = st.button("📝 Generate Script", type="primary", use_container_width=True)
with col2:
    if st.session_state.step != "input":
        reset_btn = st.button("🔄 Start Over", use_container_width=True)
        if reset_btn:
            for k in ["script", "segments", "output_dir", "video_path"]:
                st.session_state[k] = None
            st.session_state.step = "input"
            st.rerun()

# ─── Generate Script ──────────────────────────────────────────────────────────

if gen_script_btn:
    has_image = uploaded_image is not None
    if not topic.strip() and not has_image:
        st.error("Please enter a video topic or upload a reference image.")
    elif not google_api_key:
        st.error("Please enter your Google AI API key in the sidebar.")
    else:
        # Read image bytes if provided
        ref_image_bytes = None
        ref_image_mime = "image/jpeg"
        if has_image:
            uploaded_image.seek(0)
            ref_image_bytes = uploaded_image.read()
            mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "webp": "image/webp"}
            ext = uploaded_image.name.rsplit(".", 1)[-1].lower()
            ref_image_mime = mime_map.get(ext, "image/jpeg")

        spinner_msg = (
            "Analysing image and generating script with Gemini..."
            if has_image
            else "Generating script with Gemini..."
        )
        with st.spinner(spinner_msg):
            try:
                script = generate_script(
                    google_api_key=google_api_key,
                    topic=topic,
                    theme=theme,
                    target_length_seconds=target_length,
                    image_count=custom_image_count,
                    target_audience=target_audience,
                    reference_image_bytes=ref_image_bytes,
                    reference_image_mime=ref_image_mime,
                )
                st.session_state.script = script
                st.session_state.segments = script["segments"]
                st.session_state.step = "script"
            except Exception as e:
                st.error(f"Script generation failed: {e}")

# ─── Display Script ───────────────────────────────────────────────────────────

if st.session_state.step in ("script", "generate", "done") and st.session_state.script:
    script = st.session_state.script

    st.markdown("---")
    st.markdown(f"### 🎬 `{script.get('title', 'Untitled Video')}`")

    with st.expander("YouTube Description & Tags", expanded=False):
        st.text_area("Description", value=script.get("description", ""), height=80, key="desc_display")
        st.text_input("Tags", value=", ".join(script.get("tags", [])), key="tags_display")

    st.markdown(f"**{len(script['segments'])} segments · ~{script.get('total_estimated_duration', target_length)}s total**")

    # Editable script segments
    with st.expander("Script Segments (click to edit)", expanded=True):
        edited_segments = []
        for seg in st.session_state.segments:
            idx = seg["index"]
            st.markdown(f"<div class='segment-card'>", unsafe_allow_html=True)
            col_a, col_b = st.columns([1, 12])
            with col_a:
                st.markdown(f"<div class='segment-index'>#{idx + 1}</div>", unsafe_allow_html=True)
            with col_b:
                narration = st.text_area(
                    f"Narration #{idx + 1}",
                    value=seg["narration"],
                    height=80,
                    key=f"narration_{idx}",
                    label_visibility="collapsed",
                )
                scene = st.text_area(
                    f"Image Prompt #{idx + 1}",
                    value=seg["scene_description"],
                    height=60,
                    key=f"scene_{idx}",
                    label_visibility="collapsed",
                )
                caption_text = st.text_input(
                    f"Caption #{idx + 1}",
                    value=seg.get("caption", ""),
                    key=f"caption_{idx}",
                    label_visibility="collapsed",
                    placeholder="Short caption (optional)",
                )
            st.markdown("</div>", unsafe_allow_html=True)

            edited_segments.append({
                **seg,
                "narration": narration,
                "scene_description": scene,
                "caption": caption_text,
            })

        # Update session state with any edits
        st.session_state.segments = edited_segments

    # ── Generate Video button ──────────────────────────────────────────────────

    if st.session_state.step in ("script", "generate"):
        st.markdown("---")
        gen_video_btn = st.button(
            "🎥 Generate Full Video",
            type="primary",
            use_container_width=True,
            disabled=not (google_api_key and elevenlabs_api_key),
        )
        if not elevenlabs_api_key:
            st.warning("Add your ElevenLabs API key in the sidebar to generate voice narration.")

        if gen_video_btn:
            st.session_state.step = "generate"

            # Create a fresh output directory for this run
            output_dir = os.path.join(
                os.path.dirname(__file__),
                "output",
                f"video_{int(time.time())}",
            )
            os.makedirs(output_dir, exist_ok=True)
            st.session_state.output_dir = output_dir

            segments = st.session_state.segments

            # ── Phase 1: Generate images ────────────────────────────────────
            st.markdown("#### Phase 1 of 3: Generating Images")
            img_progress = st.progress(0)
            img_status = st.empty()
            total_segs = len(segments)

            def img_cb(idx, total):
                img_progress.progress((idx + 1) / total)
                img_status.text(f"Generated image {idx + 1} of {total}")

            try:
                segments = generate_all_images(
                    google_api_key=google_api_key,
                    segments=segments,
                    output_dir=output_dir,
                    width=resolution[0],
                    height=resolution[1],
                    progress_callback=img_cb,
                )
                img_status.success(f"All {total_segs} images generated.")
            except Exception as e:
                st.error(f"Image generation failed: {e}")
                st.session_state.step = "script"
                st.stop()

            # ── Phase 2: Generate voice narration ───────────────────────────
            st.markdown("#### Phase 2 of 3: Generating Voice Narration")
            voice_progress = st.progress(0)
            voice_status = st.empty()

            def voice_cb(idx, total):
                voice_progress.progress((idx + 1) / total)
                voice_status.text(f"Generated audio {idx + 1} of {total}")

            try:
                segments = generate_all_voices(
                    api_key=elevenlabs_api_key,
                    segments=segments,
                    voice_id=ELEVENLABS_VOICES[voice_name]["id"],
                    output_dir=output_dir,
                    stability=voice_stability,
                    similarity_boost=voice_similarity,
                    progress_callback=voice_cb,
                )
                voice_status.success("All narration audio generated.")
            except Exception as e:
                st.error(f"Voice generation failed: {e}")
                st.session_state.step = "script"
                st.stop()

            # Redistribute segment durations so images match audio length
            segments = redistribute_durations(segments, target_length)
            st.session_state.segments = segments

            # ── Phase 3: Build video ─────────────────────────────────────────
            st.markdown("#### Phase 3 of 3: Assembling Video")
            vid_progress = st.progress(0)
            vid_status = st.empty()
            total_vid_steps = len(segments) + 2

            def vid_cb(step, total):
                vid_progress.progress(step / total)
                vid_status.text(f"Assembling... step {step} of {total}")

            output_path = os.path.join(output_dir, "final_video.mp4")
            try:
                create_video(
                    segments=segments,
                    output_path=output_path,
                    animation_style=animation_style,
                    transition_style=transition_style,
                    resolution=resolution,
                    fps=fps,
                    show_captions=show_captions,
                    progress_callback=vid_cb,
                )
                st.session_state.video_path = output_path
                st.session_state.step = "done"
                vid_status.success("Video assembled successfully!")
            except Exception as e:
                st.error(f"Video assembly failed: {e}")
                st.session_state.step = "script"
                st.stop()

            st.rerun()

# ─── Download & Preview ───────────────────────────────────────────────────────

if st.session_state.step == "done" and st.session_state.video_path:
    st.markdown("---")
    st.success("Your video is ready!")

    video_path = st.session_state.video_path

    # In-browser preview
    with open(video_path, "rb") as vf:
        video_bytes = vf.read()

    st.video(video_bytes)

    col_dl, col_info = st.columns([1, 2])
    with col_dl:
        st.download_button(
            label="⬇️ Download Video (MP4)",
            data=video_bytes,
            file_name=f"{st.session_state.script.get('title', 'youtube_video')[:50].replace(' ', '_')}.mp4",
            mime="video/mp4",
            use_container_width=True,
        )

    with col_info:
        file_size_mb = os.path.getsize(video_path) / (1024 * 1024)
        total_duration = sum(
            s.get("actual_duration", s.get("estimated_duration", 0))
            for s in st.session_state.segments
        )
        st.markdown(f"""
**Output Details**
- Resolution: `{resolution[0]}×{resolution[1]}`
- Frame Rate: `{fps} fps`
- Duration: `{total_duration:.1f}s`
- File Size: `{file_size_mb:.1f} MB`
- Segments: `{len(st.session_state.segments)}`
- Animation: `{ANIMATION_STYLES[animation_style]['label']}`
        """)

    # Export script as JSON
    with st.expander("Export Script JSON"):
        st.json(st.session_state.script)
        script_json = json.dumps(st.session_state.script, indent=2)
        st.download_button(
            "⬇️ Download Script JSON",
            data=script_json,
            file_name="script.json",
            mime="application/json",
        )

# ─── Footer ───────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    "<small>Powered by Google Gemini · ElevenLabs · MoviePy &nbsp;|&nbsp; "
    "Get API keys: <a href='https://aistudio.google.com/app/apikey'>Google AI Studio</a> · "
    "<a href='https://elevenlabs.io'>ElevenLabs</a></small>",
    unsafe_allow_html=True,
)
