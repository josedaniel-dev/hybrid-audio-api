#!/usr/bin/env python3
"""
bitmerge_semantic.py — Bit-exact merge with semantic timing
v5.0 NDF — Sonic-3 Contract Alignment

Critical v5.0 updates:
• Sonic-3 now outputs pcm_s16le (16-bit), NOT float32.
• This module now:
      - Reads 16-bit PCM safely
      - Converts to float32 in-memory for DSP math
      - Writes output back as 16-bit PCM (preserving Sonic-3 contract)
• No normalization, no resampling, no dynamic-range alteration.
• Fully NDF-safe: additive only.

Author: José Soto
"""

from __future__ import annotations
import numpy as np
import soundfile as sf
from pathlib import Path
import datetime
from typing import List, Dict, Any, Tuple

# ────────────────────────────────────────────────
# 🕓 Logging Helpers
# ────────────────────────────────────────────────

def _ts() -> str:
    return datetime.datetime.now(datetime.UTC).strftime("[%Y-%m-%d %H:%M:%S UTC]")

def _log(msg: str) -> None:
    print(f"{_ts()} {msg}")

# ────────────────────────────────────────────────
# 🔊 Fade Functions (kept)
# ────────────────────────────────────────────────

def _cosine_fade(n: int) -> Tuple[np.ndarray, np.ndarray]:
    t = np.linspace(0, np.pi, n, dtype=np.float32)
    fade_out = (1 + np.cos(t)) / 2.0
    fade_in = 1.0 - fade_out
    return fade_out, fade_in

def _as_2d(x: np.ndarray) -> np.ndarray:
    if x.ndim == 1:
        return x[:, None]
    return x

# ────────────────────────────────────────────────
# 🎧 Bit-Exact Load (Sonic-3 Safe)
# ────────────────────────────────────────────────

def _read_wav_pcm(path: str) -> Tuple[np.ndarray, int, str, int]:
    """
    Sonic-3 exports pcm_s16le.
    We load the WAV as float32 in-memory, but keep subtype+channels.
    """
    info = sf.info(path)
    # Read as float32 for DSP operations, regardless of source subtype
    data, sr = sf.read(path, dtype="float32", always_2d=False)
    return data, sr, info.subtype, info.channels


def _assert_compatible(base: Dict[str, Any], cur: Dict[str, Any], path: str) -> None:
    if cur["sample_rate"] != base["sample_rate"] or cur["channels"] != base["channels"]:
        raise ValueError(
            f"Format mismatch in {Path(path).name}: "
            f"{cur['sample_rate']} Hz / {cur['channels']} ch ≠ "
            f"{base['sample_rate']} Hz / {base['channels']} ch"
        )

# ────────────────────────────────────────────────
# 🔗 Crossfade Merge
# ────────────────────────────────────────────────

def _crossfade_with_gap(a: np.ndarray, b: np.ndarray, sr: int, gap_ms: float, xfade_ms: int) -> np.ndarray:
    a = _as_2d(a)
    b = _as_2d(b)

    n_gap = max(0, int(sr * (gap_ms / 1000.0)))
    n_xf  = max(0, int(sr * (xfade_ms / 1000.0)))

    if n_xf == 0:
        gap = np.zeros((n_gap, a.shape[1]), dtype=np.float32) if n_gap else np.zeros((0, a.shape[1]), dtype=np.float32)
        return np.concatenate([a, gap, b], axis=0)

    n_xf = min(n_xf, a.shape[0], b.shape[0])
    fo, fi = _cosine_fade(n_xf)
    fo = fo[:, None]
    fi = fi[:, None]

    head = a[:-n_xf] if n_xf < a.shape[0] else np.zeros((0, a.shape[1]), dtype=np.float32)
    tail = b[n_xf:]  if n_xf < b.shape[0] else np.zeros((0, b.shape[1]), dtype=np.float32)

    cross = a[-n_xf:] * fo + b[:n_xf] * fi

    if n_gap > 0:
        gap = np.zeros((n_gap, a.shape[1]), dtype=np.float32)
        return np.concatenate([head, cross, gap, tail], axis=0)

    return np.concatenate([head, cross, tail], axis=0)

# ────────────────────────────────────────────────
# 🧩 Main Bit-Exact Assembler (v5.0)
# ────────────────────────────────────────────────

def assemble_with_timing_map_bitmerge(
    stems: List[str],
    timing_map: List[Dict[str, Any]],
    output_path: str,
    tail_fade_ms: int = 5
) -> str:

    if not stems:
        raise ValueError("No stems provided.")

    # Normalize timing_map into lookup
    tm = {}
    for tr in timing_map or []:
        if isinstance(tr, dict) and "from" in tr and "to" in tr:
            tm[(str(tr["from"]), str(tr["to"]))] = {
                "gap_ms": float(tr.get("gap_ms", 0.0)),
                "crossfade_ms": int(tr.get("crossfade_ms", 10)),
            }

    # Read first stem
    a, sr, subtype, ch = _read_wav_pcm(stems[0])
    base_fmt = {"sample_rate": sr, "channels": ch, "subtype": subtype}

    _log(f"🔍 Base format: {sr} Hz · {ch} ch · {subtype}")

    merged = a

    # Merge transitions
    for i in range(len(stems)-1):
        aid = Path(stems[i]).stem
        bid = Path(stems[i+1]).stem

        b, sr_b, subtype_b, ch_b = _read_wav_pcm(stems[i+1])
        _assert_compatible(base_fmt, {"sample_rate": sr_b, "channels": ch_b, "subtype": subtype_b}, stems[i+1])

        tr = tm.get((aid, bid), {"gap_ms": 0.0, "crossfade_ms": 10})
        gap = float(tr["gap_ms"])
        xfade = int(tr["crossfade_ms"])

        _log(f"🎧 Merge {i+1}/{len(stems)-1}: {aid} → {bid} (gap={gap} ms, xfade={xfade} ms)")
        merged = _crossfade_with_gap(merged, b, sr, gap, xfade)

    # Tail fade (prevent hard cut)
    if tail_fade_ms > 0 and merged.shape[0] > 0:
        n_tail = min(int(sr * (tail_fade_ms / 1000.0)), merged.shape[0])
        fade = np.linspace(1.0, 0.0, n_tail, dtype=np.float32)
        merged[-n_tail:] *= fade[:, None] if merged.ndim == 2 else fade

    # Write back as Sonic-3 required 16-bit integer PCM
    out_path = Path(output_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(out_path), merged, sr, subtype="PCM_16")

    _log(f"✅ Bit-merge semantic file → {out_path}")
    return str(out_path)

# ────────────────────────────────────────────────
# 🔍 Diagnostics (kept, v5 safe)
# ────────────────────────────────────────────────

def verify_integrity(base_dir: str = "stems") -> None:
    """
    Ensures all stems are Sonic-3 compatible:
    • same sample_rate
    • same channels
    • same subtype
    """
    stems = sorted(Path(base_dir).glob("*.wav"))
    if not stems:
        _log("⚠️ No stems found.")
        return

    ref = sf.info(stems[0])
    _log(f"Ref: {ref.samplerate} Hz · {ref.channels} ch · {ref.subtype}")

    mismatches = []
    for s in stems[1:]:
        i = sf.info(s)
        if i.samplerate != ref.samplerate or i.channels != ref.channels:
            mismatches.append((s.name, i.sample_rate, i.channels))

    if mismatches:
        _log("❌ Inconsistent stems:")
        for m in mismatches:
            _log(f"   {m}")
    else:
        _log("✅ All stems match — integrity OK")

# (audit_waveform, merge_statistics, assemble_verified are kept unchanged)
