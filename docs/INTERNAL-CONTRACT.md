# Hybrid Audio API — **Sonic-3 Internal Contract**

Version 5.3
Internal Technical Standard for full compatibility across:
Backend · CLI · UI · Rotational Engine · Stems · Templates · GCS · Cartesia Sonic-3

---

## 1. Sonic-3 Payload Contract

Every request to the generator must follow:

```
model_id: "sonic-3"
transcript: "<plain text>"
voice:
  mode: "id"
  id: <VOICE_ID>
generation_config:
  speed: <float>       # > 0
  volume: <float>      # > 0
output_format:
  container: "wav"
  encoding: "pcm_s16le"
  sample_rate: 48000
```

Rules:

* `transcript` must be plain text only.
* Required headers:

  * `X-Cartesia-Api-Key`
  * `X-Cartesia-Version`
* Output always: **WAV PCM S16LE · 48 kHz · mono**.

---

## 2. Naming Rules

### Stems

```
stem.name.<slug>.wav
stem.developer.<slug>.wav
stem.script.<slug>.wav
stem.generic.<slug>.wav
silence.<duration>ms.wav
```

### Outputs

```
output.<name>.<developer>.<timestamp>.<merge_mode>.wav
```

### Slugs

* lower case
* spaces → `_`
* invalid characters → `_`
* timestamps use UTC `%Y%m%d_%H%M%S`

---

## 3. Template Contract

A valid template must follow:

```
{
  "template_name": "double_anchor_hybrid_v3_5",
  "segments": [
      { "id": "intro", "text": "Hello {first_name}", "break_ms": 100 },
      ...
  ],
  "placeholders": { ... }
}
```

Rules:

* `segments` cannot be empty
* each `id` must be unique
* `text` must be plain text
* numeric fields allowed:

  * `gap_ms`
  * `crossfade_ms`
  * `break_ms`
  * `estimated_duration_ms`
    All must be ≥ 0
* Silences resolved via:
  `silence.<n>ms.wav`

---

## 4. Timing Rules

* `timing_map` must be an ordered list
* all transition IDs must exist
* `gap_ms`, `crossfade_ms`, `break_ms` ≥ 0
* missing silences are generated automatically
* guarantees:

  * never negative
  * never NaN
  * silence resolved before merge
  * stable temporal order

---

## 5. Stems and Outputs

### Local folders

```
stems/
output/
```

### Mandatory WAV validation

All assets must be:

* PCM S16LE
* 48000 Hz
* mono
* size > 0
* no clipping
* no NaN/Inf

### Pre-merge integrity checks

* amplitude scan
* peak scan
* optional normalization (template-dependent)

---

## 6. Google Cloud Storage (Optional)

Enabled when:

* bucket configured
* valid credentials

Rules:

* remote paths mirror local structure
* `build_gcs_blob_path()` defines blob paths
* `build_gcs_uri()` defines public/signed URLs
* missing blobs return `gcs_uri = null`

### Consistency Engine

Valid comparisons:

```
match
local_only
gcs_only
missing
```

---

## 7. Error Model

### Sonic-3 errors

* `Sonic3Error`
* `InvalidPayloadError`
* `VoiceIncompatibleError`
* `RateLimitError`

### Internal errors

* `TemplateError`
* `TimingError`
* `BucketAccessError`
* `WavValidationError`
* `MergeIntegrityError`

Standard response:

```
{
  "error": "<type>",
  "message": "<details>",
  "hint": "<optional recovery hint>"
}
```

---

## 8. Regeneration Pipeline

Before regenerating:

1. Remove legacy stems
2. Regenerate:

   * names
   * developers
   * generic
   * silence stems
   * template stems
3. Write a new `stems_index.json` containing:

```
audio_format
encoding
sample_rate
cartesia_version
contract_signature
timestamp
metadata: { ... }
```

---

## 9. UI / CLI / Tools Integration

Every external tool must:

* use `build_sonic3_payload()`
* validate templates with the internal validator
* display WAV attributes:

  * format
  * duration
  * size
  * timestamps
  * paths
  * signed URLs (if any)
* fully respect:

  * naming rules
  * timing rules
  * payload contract
  * merge semantics

---

## 10. Compatibility Rules

* never rename existing stems
* never alter previous merges
* never break HTTP or CLI routes
* never change output formats
* never modify timestamp semantics
