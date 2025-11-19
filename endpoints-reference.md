
# **Hybrid Audio API — Endpoint Reference (Sonic-3 Edition)**

**Author:** José Daniel Soto
**Version:** v5.x NDF — Modular Router Architecture
**Document Purpose:** Provide a clear, precise description of every route, its function, parameters, return structure, and when it should be used.

---

# **1. Overview**

The Hybrid Audio API is designed to generate **personalized voice stems** and **fully assembled audio messages** using the **Cartesia Sonic-3 TTS engine**, with features including:

* Deterministic stem generation
* Semantic bit-merge audio assembly
* Rotational datasets
* Cache system with metadata
* Dataset ingestion
* Optional Google Cloud Storage integration
* Request context observability

The API is fully modular, with routes organized as:

| Router                 | Purpose                                       |
| ---------------------- | --------------------------------------------- |
| `/generate`            | Stem creation (name, developer, pairs)        |
| `/assemble`            | Template-based or raw assembly                |
| `/rotation`            | Fair round-robin dataset rotation             |
| `/cache`               | Cache listing, invalidation, batch generation |
| `/external`            | Uploading and previewing datasets             |
| `/health` & `/version` | Base system diagnostics                       |

---

# **2. /generate — Stem Generation Routes**

These routes produce **individual WAV stems** used in message assembly.

---

## **POST /generate/name**

Generate or return cached **name stem**.

### **Body**

```json
{
  "name": "John",
  "voice_id": "optional"
}
```

### **Behavior**

* Creates a stem called `stem.name.john.wav`
* Uses cache if already generated
* Uses Sonic-3 through `cartesia_generate()`

### **Use Case**

Calling name stems directly or preparing batch outputs.

---

## **POST /generate/developer**

Generate or reuse **developer brand stem**.

### **Body**

```json
{
  "developer": "Hilton",
  "voice_id": "optional"
}
```

### **Use Case**

Required for templates using `{developer}`.

---

## **POST /generate/combined**

Generate **both name and developer** stems in a single request.

### **Body**

```json
{
  "name": "John",
  "developer": "Hilton"
}
```

### **Response**

* Returns both stem paths
* Extended mode includes cache metadata

### **Use Case**

UI or CLI when pre-building pairs.

---

## **GET /generate/check/stem_in_bucket**

Verifies a stem’s existence in GCS.

Parameters:

```
label=<stem.name.john>
```

Returns:

* exists
* signed_url
* resolved_uri

---

## **GET /generate/check/stem_path**

Diagnostic endpoint returning:

* local path
* remote GCS path (if exists)
* cache metadata

---

# **3. /assemble — Assembly Routes**

These routes generate **full personalized WAV output**.

---

## **POST /assemble/template**

Main Sonic-3 assembly workflow.

### **Body**

```json
{
  "first_name": "John",
  "developer": "Hilton",
  "template": "double_anchor_hybrid.json",
  "upload": false
}
```

### **Behavior**

1. Loads the template
2. Applies `{name}` and `{developer}`
3. Generates or reuses stems
4. Applies timing map
5. Assembles via **bit-merge**
6. Optionally uploads to GCS

### **Use Case**

Main entrypoint for production calls.

---

## **POST /assemble/segments**

Manual assembly using raw text segments.

### **Body**

```json
{
  "segments": ["Hello", "John", "from Hilton"],
  "segment_ids": ["seg1", "seg2", "seg3"],
  "upload": false
}
```

### **Use Case**

Testing, debugging, or custom pipelines not based on templates.

---

## **GET /assemble/output_location**

Returns the most recently generated output WAV file.

Useful for CLI and development environments.

---

## **GET /assemble/check/stem_in_bucket**

Checks if a **stem** is present in GCS.

---

## **GET /assemble/check/output_in_bucket**

Checks if a **final assembled output** is present in GCS.

---

# **4. /rotation — Dataset Rotation**

Implements **fair rotation** across names and developers.

---

## **GET /rotation/next_name**

Returns the next name according to least-used and oldest-used rules.

---

## **GET /rotation/next_developer**

Same as above, but for developers.

---

## **GET /rotation/next_pair**

Returns both name and developer:

```json
{
  "ok": true,
  "name": "John",
  "developer": "Hilton",
  "timestamp": "..."
}
```

---

## **POST /rotation/generate_pair**

Automatically:

* Fetches next pair
* Generates both stems (cached or fresh)
* Returns metadata

### **Body**

```json
{
  "voice_id": "optional",
  "extended": false
}
```

---

## **GET /rotation/check_bucket**

Bucket verification helper for stems.

---

## **GET /rotation/pairs_stream**

Returns a sequence of upcoming rotation pairs for UI previews.

---

# **5. /cache — Cache & Batch Engine**

Handles the system’s stem cache and batch operations.

---

## **GET /cache/list**

Returns:

* Cache summary
* Full index
* Compatibility metadata
* Extended Sonic-3 contract signatures (if present)

### Extended Mode:

`/cache/list?extended=true`

Includes:

* audio_format
* encoding
* cartesia_version
* contract signature
* stale/legacy bit flags

---

## **POST /cache/invalidate**

Delete a stem from cache.

### **Body**

```json
{
  "stem_name": "stem.name.john"
}
```

---

## **POST /cache/bulk_generate**

Batch generation for datasets.

### **Body**

```json
{
  "names_path": "data/common_names.json",
  "developers_path": "data/developer_names.json"
}
```

---

# **6. /external — Dataset Intake**

Upload, preview, and update datasets.

---

## **POST /external/upload_base**

Uploads CSV/JSON and writes to:

* `data/common_names.json`
* `data/developer_names.json`
* `data/<custom>.json`

### **Form Fields**

* `dataset_role`: names | developers | custom
* `target_name`: optional
* `file`: UploadFile

---

## **POST /external/preview**

Same parsing logic as upload, but **does not save**.

Returns:

* detected type
* parsed items
* count
* sample

---

# **7. Root System Endpoints**

Provided by `fastapi_server.py`.

---

## **GET /health**

Returns:

* api version
* active model
* voice_id
* config summary
* request_id (if observability is enabled)

---

## **GET /health/extended**

Adds:

* GCS healthcheck
* extra timestamps

---

## **GET /live**

Container/Kubernetes liveness probe.

---

## **GET /ready**

Readiness probe ensuring config load & environment integrity.

---

## **GET /version**

Minimal version descriptor.

---

# **8. Missing But Mentioned Endpoints (Future Work)**

These are **planned** in your roadmap but **not yet implemented**:

| Endpoint             | Status    |
| -------------------- | --------- |
| `/integrity/stems`   | ❌ Missing |
| `/integrity/outputs` | ❌ Missing |
| `/validate/output`   | ❌ Missing |
| `/regenerate/all`    | ❌ Missing |

These require Phase-1 + Phase-2 files you plan to add.

---

# **9. Summary**

Hybrid Audio API currently includes:

* Full stem generation suite
* Complete template-based assembly
* Raw assembly
* Rotational scheduling
* Cache management
* Dataset ingestion
* GCS integration
* System health endpoints

Everything is stable, consistent, and aligned with the Sonic-3 payload contract—pending the additional modules required for validation, regeneration, and integrity auditing.



