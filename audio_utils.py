"""
audio_utils.py — Normalization & Clean Merge Utilities
──────────────────────────────────────────────────────────────
v5.0 NDF — Sonic-3 Contract Alignment
• Enforces uniform 48k / pcm_s16le WAV (Cartesia-mandated)
• Removes dependency on mismatched formats from prior versions
• Normalization now strictly optional (env-driven)
• Clean merge path guaranteed contract-safe
• NO resampling, NO float32 conversions unless explicitly enabled
• Fully backward compatible with bitmerge_semantic
"""

import math
from pathlib import Path
from typing import Optional, Tuple, Any, List
from pydub import AudioSegment
from pydub.effects import normalize as peak_normalize

from config import (
    LUFS_TARGET,
    CROSSFADE_MS,
    DEBUG,
    DISABLE_NORMALIZATION,
    SAMPLE_RATE,
    OUTPUT_DIR,
)

# bitmerge semantic merge
try:
    from bitmerge_semantic import assemble_with_timing_map_bitmerge
except ImportError:
    assemble_with_timing_map_bitmerge = None


# ============================================================
# 🚀 Utility: timestamp naming (local, safe)
# ============================================================

def _timestamped_filename(name: str, developer: str, ext: str = "wav") -> str:
    from datetime import datetime
    tag = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    n = name.strip().replace(" ", "_")
    d = developer.strip().replace(" ", "_")
    return f"{n}_{d}_{tag}.{ext}"


# ============================================================
# 🎚️ Core Normalization (optional)
# ============================================================

def normalize_audio(audio: AudioSegment, target_lufs: float = LUFS_TARGET) -> AudioSegment:
    """Approximate LUFS normalization (only active if enabled)."""
    if DISABLE_NORMALIZATION:
        return audio

    if audio.rms == 0:
        return audio

    rms = audio.rms
    current_dbfs = 20 * math.log10(rms / (audio.max_possible_amplitude or 1))
    gain = max(min(target_lufs - current_dbfs, 12), -12)
    return audio.apply_gain(gain)


def peak_normalize_audio(audio: AudioSegment) -> AudioSegment:
    """Peak normalization (optional, env controlled)."""
    if DISABLE_NORMALIZATION:
        return audio
    return peak_normalize(audio)


def full_normalize(audio: AudioSegment) -> AudioSegment:
    """LUFS leveling → peak normalization."""
    if DISABLE_NORMALIZATION:
        return audio
    return peak_normalize_audio(normalize_audio(audio))


# ============================================================
# 🧪 Loading & Metadata
# ============================================================

def load_clip(path: str) -> AudioSegment:
    clip = AudioSegment.from_file(path)

    # Sonic-3 contract: must be 48k & 16-bit
    if clip.frame_rate != SAMPLE_RATE:
        if DEBUG:
            print(f"⚠️ WARNING: Clip {path} has frame_rate {clip.frame_rate}, expected {SAMPLE_RATE}")
    return clip


def clip_signature(clip: AudioSegment) -> Tuple[int, int, int]:
    """Returns (frame_rate, bit_depth, channels)."""
    return (clip.frame_rate, clip.sample_width * 8, clip.channels)


def read_info(path: str) -> dict:
    clip = load_clip(path)
    return {
        "duration_ms": len(clip),
        "frame_rate": clip.frame_rate,
        "sample_width_bits": clip.sample_width * 8,
        "channels": clip.channels,
        "dBFS": round(clip.dBFS, 2) if clip.rms else None,
    }


def ensure_same_format(a: AudioSegment, b: AudioSegment):
    """Checks format consistency."""
    if clip_signature(a) != clip_signature(b):
        raise ValueError(
            f"Format mismatch: {clip_signature(a)} vs {clip_signature(b)} — "
            f"all stems MUST be Sonic-3 (48kHz, pcm_s16le)."
        )


# ============================================================
# 🔗 Append Helpers
# ============================================================

def append_with_crossfade(base: AudioSegment, nxt: AudioSegment, crossfade_ms: int = CROSSFADE_MS) -> AudioSegment:
    return base.append(nxt, crossfade=crossfade_ms)


def append_minimal(base: AudioSegment, nxt: AudioSegment,
                   tiny_crossfade_ms: int = 8,
                   strict_format: bool = True) -> AudioSegment:

    if strict_format:
        ensure_same_format(base, nxt)

    return base.append(nxt, crossfade=max(0, tiny_crossfade_ms))


# ============================================================
# 🧩 Clean Merge Assembly (Sonic-3 Safe)
# ============================================================

def assemble_clean_merge(stem_paths: List[str], output_path: str, crossfade_ms: int = 8) -> str:
    if not stem_paths:
        raise ValueError("No stems provided.")

    clips = [load_clip(p) for p in stem_paths]
    base_sig = clip_signature(clips[0])

    # Validate all stems
    for p, c in zip(stem_paths, clips):
        if clip_signature(c) != base_sig:
            raise ValueError(f"Format mismatch in {p}: {clip_signature(c)} vs {base_sig}")

    # Merge
    merged = clips[0]
    for nxt in clips[1:]:
        merged = append_minimal(merged, nxt, tiny_crossfade_ms=crossfade_ms, strict_format=False)

    # Optional normalization
    merged = full_normalize(merged)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    merged.export(output_path, format="wav")

    if DEBUG:
        print(f"✅ Clean merge saved → {output_path}")

    return str(output_path)


# ============================================================
# 📦 Timestamped Clean Merge (fallback templates)
# ============================================================

def clean_merge_timestamped(stem_paths: List[str], name: str, developer: str) -> str:
    filename = _timestamped_filename(name, developer)
    out = OUTPUT_DIR / filename
    return assemble_clean_merge(stem_paths, str(out))


# ============================================================
# 🧭 Semantic Timing Wrapper (bit-exact)
# ============================================================

def assemble_with_timing_map(stems: List[str], timing_map: Any, output_path: str) -> str:
    if not stems:
        raise ValueError("No stems provided for semantic assembly.")

    if isinstance(timing_map, list) and assemble_with_timing_map_bitmerge:
        if DEBUG:
            print("🔊 Using bit-exact merge (bitmerge_semantic)…")
        return assemble_with_timing_map_bitmerge(stems, timing_map, output_path)

    # Legacy fallback
    if DEBUG:
        print("🧭 Using legacy semantic merge…")

    clips = [load_clip(p) for p in stems]
    merged = clips[0]
    for nxt in clips[1:]:
        merged = append_minimal(merged, nxt, tiny_crossfade_ms=10, strict_format=False)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    merged.export(output_path, format="wav")

    return str(output_path)


# ============================================================
# 🔐 Rotational Safe Merge
# ============================================================

def safe_merge_stems(stems: List[str], output_path: str) -> str:
    clips = [load_clip(p) for p in stems]
    merged = clips[0]

    for nxt in clips[1:]:
        merged = append_minimal(merged, nxt, tiny_crossfade_ms=8, strict_format=False)

    merged = full_normalize(merged)

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    merged.export(output_path, format="wav")

    if DEBUG:
        print(f"🎧 Rotational-safe merge saved → {output_path}")

    return str(output_path)


# ============================================================
# 🧪 Diagnostics
# ============================================================

def describe(audio: AudioSegment) -> dict:
    if len(audio) == 0:
        return {"error": "empty_audio"}

    return {
        "duration_sec": round(len(audio) / 1000, 2),
        "rms": audio.rms,
        "dBFS": round(audio.dBFS, 2),
        "frame_rate": audio.frame_rate,
        "sample_width_bits": audio.sample_width * 8,
        "channels": audio.channels,
        "target_lufs": LUFS_TARGET,
    }


if __name__ == "__main__":
    print("🎚️ audio_utils v5.0 NDF — Sonic-3 aligned, normalization optional.")
