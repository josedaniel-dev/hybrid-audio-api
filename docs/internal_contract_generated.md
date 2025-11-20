# Hybrid Audio API — Sonic-3 Hardened (Auto-Generated Overview)

This document summarizes the Sonic-3 contract, naming rules, validation layers, and audit utilities currently available in the codebase. It is derived from the active helpers and validators to support UI/CLI integrations and operational audits.

## Contract Core
- **Model:** `sonic-3`
- **Container:** `wav`
- **Encoding:** `pcm_s16le`
- **Sample rate:** `48000`
- **Voice mode:** `id`
- **Transcript:** plain text (no SSML)
- **Contract signature:** produced via `contract_signature.compute_contract_signature()`

## Naming Rules
- Stems: `stem.<kind>.<slug>.wav` where kind ∈ {`name`, `developer`, `generic`, `segment`}
- Silence: `silence.<duration>ms.wav`
- Segments: `segment.<slug>.wav`
- Outputs: `output.<name>.<developer>.<timestamp>.<merge_mode>.wav`

## Validators
| Module | Functions | Purpose |
| --- | --- | --- |
| `template_validator` | `validate_template_structure`, `validate_segments`, `validate_placeholders`, `validate_no_ssml`, `validate_timing` | Base structural and content checks |
| `template_validator` (full) | `validate_template_full` | Graph connectivity, cycles, placeholder coverage, timing coherence |
| `timing_sanitizer` | `validate_timing_map`, `normalize_breaks`, `resolve_silence_stems`, `validate_graph_structure`, `auto_fill_missing_transitions`, `enforce_exclusive_break_vs_crossfade` | Timing map sanitation and graph safety |
| `validator_audio` | `validate_wav_header`, `validate_sample_rate`, `validate_channels`, `validate_encoding`, `validate_duration`, `validate_merge_integrity`, `compute_sha256`, `compute_rms`, `detect_clipped_samples`, `detect_silence_regions` | WAV compliance, integrity, and metrics |

## Regeneration Pipeline
- Entry point: `regenerate_all.regenerate_all()`
- Generates stems for names, developers, generic template text, segment stems, and silence assets.
- Rewrites `stems_index.json` with metadata including format, encoding, sample rate, bit depth, channels, sha256, stem type, and contract signature.

## Integrity & GCS
- FastAPI routes under `routes/integrity.py` expose `/integrity/stems`, `/integrity/outputs`, and `/integrity/stems-index` for local/GCS comparison and WAV health.
- GCS helpers: `gcs_consistency.compare_local_vs_gcs`, `gcs_has_file`, `local_has_file`.

## Cartesia Client
- `cartesia_client.safe_generate_wav()` wraps payload construction, validation, request/response logging, and WAV validation for Sonic-3.

## Usage Notes
- Silence stems are generated on-demand via `silence_generator.ensure_silence_stem_exists` and follow the naming contract.
- Template graph checks enforce that breaks and crossfades remain mutually exclusive and that timing graphs are acyclic with a single root.
- For audits, `validator_audio.compute_sha256`, `compute_rms`, and `detect_clipped_samples` feed integrity responses and the stems index metadata.

