"""ElevenLabs TTS voice generator for video narration segments."""

import os
import time
import requests
from pydub import AudioSegment


ELEVENLABS_BASE_URL = "https://api.elevenlabs.io/v1"

# Free-tier compatible model (lower latency, works on all tiers)
DEFAULT_MODEL = "eleven_multilingual_v2"


def generate_voice(
    api_key: str,
    text: str,
    voice_id: str,
    output_path: str,
    stability: float = 0.50,
    similarity_boost: float = 0.75,
    style: float = 0.0,
    retries: int = 3,
) -> str:
    """
    Generate TTS audio for text using ElevenLabs and save as MP3.
    Returns the saved file path.
    """
    url = f"{ELEVENLABS_BASE_URL}/text-to-speech/{voice_id}"
    headers = {
        "Accept": "audio/mpeg",
        "Content-Type": "application/json",
        "xi-api-key": api_key,
    }
    payload = {
        "text": text,
        "model_id": DEFAULT_MODEL,
        "voice_settings": {
            "stability": stability,
            "similarity_boost": similarity_boost,
            "style": style,
            "use_speaker_boost": True,
        },
    }

    last_error = None
    for attempt in range(retries):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=60)

            if response.status_code == 401:
                raise ValueError("Invalid ElevenLabs API key")
            if response.status_code == 429:
                # Rate limited — wait before retry
                time.sleep(5 * (attempt + 1))
                continue
            if response.status_code != 200:
                raise RuntimeError(
                    f"ElevenLabs API error {response.status_code}: {response.text[:200]}"
                )

            os.makedirs(os.path.dirname(output_path), exist_ok=True)
            with open(output_path, "wb") as f:
                f.write(response.content)

            return output_path

        except (ValueError, RuntimeError):
            raise
        except Exception as e:
            last_error = e
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            continue

    raise RuntimeError(f"Voice generation failed after {retries} attempts: {last_error}")


def get_audio_duration_seconds(audio_path: str) -> float:
    """Return the duration of an audio file in seconds using pydub."""
    audio = AudioSegment.from_file(audio_path)
    return len(audio) / 1000.0


def generate_all_voices(
    api_key: str,
    segments: list,
    voice_id: str,
    output_dir: str,
    stability: float = 0.50,
    similarity_boost: float = 0.75,
    progress_callback=None,
) -> list:
    """
    Generate narration audio for every segment.
    Populates each segment with 'audio_path' and 'actual_duration'.
    progress_callback(segment_index, total) is called after each audio file completes.
    """
    total = len(segments)

    for seg in segments:
        idx = seg["index"]
        output_path = os.path.join(output_dir, f"audio_{idx:03d}.mp3")

        if os.path.exists(output_path):
            seg["audio_path"] = output_path
            seg["actual_duration"] = get_audio_duration_seconds(output_path)
            if progress_callback:
                progress_callback(idx, total)
            continue

        generate_voice(
            api_key=api_key,
            text=seg["narration"],
            voice_id=voice_id,
            output_path=output_path,
            stability=stability,
            similarity_boost=similarity_boost,
        )

        seg["audio_path"] = output_path
        seg["actual_duration"] = get_audio_duration_seconds(output_path)

        if progress_callback:
            progress_callback(idx, total)

    return segments


def list_available_voices(api_key: str) -> list[dict]:
    """Fetch available voices from ElevenLabs (includes free voices)."""
    url = f"{ELEVENLABS_BASE_URL}/voices"
    headers = {"xi-api-key": api_key}
    response = requests.get(url, headers=headers, timeout=10)
    if response.status_code != 200:
        return []
    data = response.json()
    return [
        {
            "name": v["name"],
            "id": v["voice_id"],
            "description": v.get("description", ""),
            "labels": v.get("labels", {}),
        }
        for v in data.get("voices", [])
    ]
