# Hybrid Audio API — Sonic-3 Internal Contract

## Sonic-3 Payload Contract
- **model_id**: `sonic-3`
- **transcript**: plain text only (no SSML or markup).
- **voice**: `{ "mode": "id", "id": VOICE_ID }`
- **generation_config**: `speed` and `volume` are floats > 0.
- **output_format**:
  - `container`: `wav`
  - `encoding`: `pcm_s16le`
  - `sample_rate`: `48000`
- All requests must include the Cartesia version header and API key.

## Naming Rules
- **Stems**
  - `stem.name.<slug>.wav`
  - `stem.developer.<slug>.wav`
  - `stem.generic.<slug>.wav`
  - `silence.<duration>ms.wav`
- **Outputs**
  - `output.<name>.<developer>.<timestamp>.<merge_mode>.wav`
  - Timestamp format: `%Y%m%d_%H%M%S` (UTC).
- Slugs are lowercased, trimmed and non-alphanumeric characters become `_`.

## Template System
- Templates must declare `template_name` and a non-empty `segments` list.
- Segment IDs are unique and non-empty; text must be plain string content.
- Allowed numeric fields: `gap_ms`, `crossfade_ms`, `break_ms`, `estimated_duration_ms` — all non-negative.
- Placeholders discovered in text must be declared under `placeholders` when present.
- Absolutely no SSML tags in any segment text.

## Timing Rules
- `timing_map` is a list of transitions referencing valid segment IDs.
- `gap_ms` and `crossfade_ms` in transitions must be numeric and >= 0.
- `break_ms` in segments is materialized into `silence.<duration>ms.wav` via `silence_generator.ensure_silence_stem_exists`.
- Timing sanitization guarantees non-negative values and resolves silence stems before assembly.

## Stems and Outputs
- Stems live in `stems/` and must adhere to naming rules above.
- Outputs are written to `output/` following the output filename contract.
- All WAV assets must validate as PCM S16LE, mono, 48 kHz with duration > 0.
- Merge integrity checks scan for NaN/Inf and clipping at full scale.

## Google Cloud Storage (GCS)
- GCS usage is optional; enabled when bucket + credentials are configured.
- Blob paths mirror local filenames inside the configured stems/output folders.
- Signed URLs are generated for existing blobs; otherwise, URLs remain null.

## Error Model
- Core exceptions:
  - `Sonic3Error` base with specialized subclasses for payloads, templates, timing, bucket access, validation, and merge integrity.
  - Cartesia client raises `Sonic3ClientError`, `InvalidPayloadError`, `VoiceIncompatibleError`, and `RateLimitError` for API-specific issues.

## Regeneration Pipeline
- Remove legacy/legacy-pattern stems before regeneration.
- Recreate stems for names, developers, generic/template segments, and all silence durations referenced by templates.
- Rewrite `stems_index.json` with keys: `audio_format`, `encoding`, `sample_rate`, `cartesia_version`, `contract_signature`, `timestamp`, plus per-stem metadata.

## Extending to UI or CLI
- Always reuse `cartesia_client.build_payload` to construct requests.
- Validate templates with `template_validator` before accepting user content.
- Inspect WAV artifacts using `validator_audio` and expose integrity metadata (headers, size, timestamps, signed URLs) in any UI/CLI diagnostic view.
- Maintain naming and timing rules to stay compatible with existing routes and assembly logic.
