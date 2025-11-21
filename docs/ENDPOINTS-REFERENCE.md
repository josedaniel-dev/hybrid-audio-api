# **Hybrid Audio API — Endpoint Reference (Sonic-3 Edition)**

**Author:** José Daniel Soto
**Version:** v5.3 NDF — Modular Router Architecture
**Document Purpose:** Provide a clear, precise description of every route, its function, parameters, return structure, and when it should be used.

---

# **1. Overview**

The Hybrid Audio API generates **personalized voice stems** and **fully assembled, production-ready WAV outputs** using the **Cartesia Sonic-3 TTS engine**, supported by:

* Deterministic stem generation
* Structured stem directory system (name/developer/script)
* Semantic bit-merge assembly
* Rotational engines (names, developers, scripts)
* Cache system with signatures + metadata
* Dataset ingestion for external CSV/JSON lists
* Optional Google Cloud Storage (GCS)
* Observability and integrity diagnostics
* Non-Destructive-Fix (NDF) development protocol

### **Modular Router Layout**

| Router      | Purpose                                        |
| ----------- | ---------------------------------------------- |
| `/generate` | Stem generation (name, developer, combined)    |
| `/assemble` | Template-based & raw assembly                  |
| `/rotation` | Round-robin dataset rotation + script rotation |
| `/cache`    | Cache listing, invalidation, batch generation  |
| `/external` | Upload, preview, and manage datasets           |
| `/health`   | System diagnostics & readiness                 |
| `/version`  | Minimal version stamp                          |

---

# **2. /generate — Stem Generation Routes**

These endpoints generate **stems** (WAV files) under the contract:

`stem.<category>.<slug>.wav`
Categories: `name`, `developer`, `script`, `generic`

All stems are stored in:

```
stems/<category>/<file>.wav
```

---

## **POST /generate/name**

Generate or retrieve a cached **name stem**.

### **Body**

```json
{
  "name": "John",
  "voice_id": "optional"
}
```

### **Result**

* Generates `stem.name.john.wav`
* Writes to `stems/name/stem.name.john.wav`
* Returns contract metadata and signature

---

## **POST /generate/developer**

Generate a **developer stem**.

### **Body**

```json
{
  "developer": "Hilton",
  "voice_id": "optional"
}
```

### Use Case

Used in all templates containing `{developer}` placeholders.

---

## **POST /generate/combined**

Generate **both name + developer** stems in one request.

### **Body**

```json
{
  "name": "John",
  "developer": "Hilton"
}
```

### Behavior

* Creates or loads both stems
* Returns combined metadata

---

# **3. /assemble — Assembly Routes**

These routes produce **full WAV messages** by joining stems, applying timing rules, and performing **semantic bit-merge**.

---

## **POST /assemble/template**

Primary assembly pipeline.

### **Body**

```json
{
  "first_name": "John",
  "developer": "Hilton",
  "template": "double_anchor_hybrid.json",
  "upload": false
}
```

### Pipeline Steps

1. Load template JSON
2. Validate with `template_validator`
3. Resolve placeholders
4. Generate stems (cached or fresh)
5. Materialize silence stems
6. Build timing map
7. Execute bit-merge
8. Optionally upload output to GCS

---

## **POST /assemble/segments**

Manual assembly using a list of stem paths.

### **Body**

```json
{
  "segments": [
    "stem.name.john.wav",
    "stem.developer.hilton.wav"
  ],
  "upload": false
}
```

### Use Case

Development, debugging, and custom pipelines.

---

## **GET /assemble/output_location**

Returns the **directory path** where assembled outputs are written.

```
{
  "output_dir": "output/"
}
```

---

# **4. /rotation — Dataset Rotation**

Rotation engine applies **least-used** selection for:

* Names
* Developers
* Script stems (v5.2+)

All rotation endpoints return deterministic, cycle-aware values.

---

## **GET /rotation/next_name**

Returns the next name in rotation.

---

## **GET /rotation/next_developer**

Same as above for developers.

---

## **GET /rotation/next_pair**

Returns:

```json
{
  "ok": true,
  "name": "John",
  "developer": "Hilton",
  "timestamp": "2025-..."
}
```

---

## **POST /rotation/generate_pair**

Generates stems for the **next pair**.

### **Body**

```json
{
  "voice_id": "optional",
  "extended": false
}
```

---

## **GET /rotation/pairs_stream?limit=N**

Returns next `N` rotational pairs for UI previews.

---

## **Script Rotation (v5.2)**

### **GET /rotation/next_script**

Returns next script label in rotation.
Example:

```
stem.script.intro_line
```

### **POST /rotation/generate_script**

Generates a single script stem.

---

### **GET /rotation/scripts_stream?limit=N**

Returns sequential script items.

---

## **GET /rotation/check_bucket**

Checks if a stem exists in GCS.

**Query**

```
label=stem.name.john
```

**Returns**

* exists (bool)
* gcs_uri
* relative_path
* blob_name
* consistency status

---

# **5. /cache — Cache & Batch Engine**

---

## **GET /cache/list**

Returns cache metadata and stem index.

### Extended mode

```
/cache/list?extended=true
```

Adds:

* contract_signature
* audio_format
* encoding
* cartesia_version
* compatibility flags

---

## **POST /cache/invalidate**

Deletes a stem from the index.

### **Body**

```json
{
  "stem_name": "stem.name.john"
}
```

---

## **POST /cache/bulk_generate**

Batch processing for names + developers datasets.

### **Body**

```json
{
  "names_path": "data/common_names.json",
  "developers_path": "data/developer_names.json"
}
```

---

## **GET /cache/check_in_bucket**

Verifies stem presence in GCS.
Uses structured path resolution internally.

---

## **GET /cache/bucket_list?prefix=stems**

Lists bucket items with optional prefix.

---

# **6. /external — Dataset Intake**

---

## **POST /external/upload_base**

Uploads lists of names/developers/custom text.

### **Form Fields**

* `file` (CSV/JSON/TXT)
* `dataset_role`: names | developers | custom
* `target_name`: optional override for custom datasets

---

## **POST /external/preview**

Parses dataset without saving.

Returns:

* detected format
* parsed list
* count
* sample values

---

## **GET /external/list**

Returns all datasets registered under `/data`.

---

## **DELETE /external/delete?filename=X**

Deletes a dataset.

---

# **7. Root / Diagnostics**

---

## **GET /health**

Returns:

* API version
* Sonic-3 model
* voice_id (if configured)
* env mode
* GCS availability
* basic runtime stats

---

## **GET /health/extended**

Adds:

* GCS bucket ping
* index statistics
* timestamps
* system footprint

---

## **GET /live**

Liveness probe.

## **GET /ready**

Readiness probe.

## **GET /version**

Tiny version descriptor.

---

# **8. Missing / Future Endpoints**

Defined in roadmap but **not yet implemented**:

| Endpoint                | Status            |
| ----------------------- | ----------------- |
| `/integrity/stems`      | ❌ NOT IMPLEMENTED |
| `/integrity/outputs`    | ❌ NOT IMPLEMENTED |
| `/validate/output`      | ❌ NOT IMPLEMENTED |
| `/regenerate/all`       | ❌ NOT IMPLEMENTED |
| `/scripts/validate_set` | ❌ NOT IMPLEMENTED |

---

# **9. Summary**

Current API includes:

* Full Sonic-3 stem generation
* Template-based message assembly
* Structured stem validation
* Rotational cycles
* Dataset ingestion
* Cache system with contract signatures
* Optional GCS sync + consistency checking
* Health and diagnostics endpoints

This version is now **fully aligned with Real Hybrid Audio API v5.3**, your restructuring work, all routers, your internal naming contracts, and your exact Sonic-3 payload rules.

---

