# **Hybrid Audio API — Endpoint Reference (Sonic-3 Edition)**

Version 5.3 — Router-Accurate Specification

# **1. Overview**

The Hybrid Audio API provides:

* Sonic-3 stem generation
* Template-based audio assembly
* Structured stems (name/developer/script)
* Rotational engines
* Cache system
* Dataset ingestion
* Optional Google Cloud Storage
* HTTP-first CLI compatibility
* Full diagnostics (`/health`, `/version`)

Routers:

| Router      | Purpose                                       |
| ----------- | --------------------------------------------- |
| `/generate` | Stem generation                               |
| `/assemble` | Template and raw assembly                     |
| `/rotation` | Round-robin rotation and script rotation      |
| `/cache`    | Cache listing, invalidation, batch operations |
| `/external` | Dataset intake                                |
| `/health`   | Diagnostics                                   |
| `/version`  | Service stamp                                 |

---

# **2. /generate — Stem Generation**

### **POST /generate/name**

Generate a name stem.

Body:

```json
{ "name": "John", "voice_id": "optional" }
```

Creates:

```
stems/name/stem.name.john.wav
```

---

### **POST /generate/developer**

Generate a developer stem.

Body:

```json
{ "developer": "Hilton", "voice_id": "optional" }
```

---

### **POST /generate/combined**

Generate both stems at once.

Body:

```json
{ "name": "John", "developer": "Hilton" }
```

---

# **3. /assemble — Assembly Pipeline**

### **POST /assemble/template**

Main assembly route for templates.

Body:

```json
{
  "first_name": "John",
  "developer": "Hilton",
  "template": "double_anchor_hybrid.json",
  "upload": false
}
```

Pipeline:

1. Load template
2. Validate
3. Resolve placeholders
4. Generate stems
5. Create silence stems
6. Build timing map
7. Bit-merge
8. Optional GCS upload

---

### **POST /assemble/segments**

Manual assembly using explicit stem filenames.

Body example:

```json
{
  "segments": [
    "stem.name.john.wav",
    "stem.developer.hilton.wav"
  ],
  "upload": false
}
```

---

### **GET /assemble/output_location**

Returns output directory path.

---

# **4. /rotation — Dataset Rotation**

### **GET /rotation/next_name**

Least-used next name in rotation.

### **GET /rotation/next_developer**

Least-used next developer.

### **GET /rotation/next_pair**

Returns:

```json
{
  "ok": true,
  "name": "John",
  "developer": "Hilton",
  "timestamp": "2025-..."
}
```

### **POST /rotation/generate_pair**

Generates stems for the next pair.

Body:

```json
{ "voice_id": "optional", "extended": false }
```

### **GET /rotation/pairs_stream?limit=N**

Returns next N pairs.

---

## **Script Rotation (v5.2+)**

### **GET /rotation/next_script**

Returns the next script stem label.

### **POST /rotation/generate_script**

Generates a script stem.

### **GET /rotation/scripts_stream?limit=N**

Same as pairs_stream, but for scripts.

---

## **GET /rotation/check_bucket**

Check if a given stem exists in GCS.

Query:

```
label=stem.name.john
```

Returns:

* exists
* blob name
* gcs_uri
* relative path
* consistency result

---

# **5. /cache — Cache Engine**

### **GET /cache/list**

Returns cache index and metadata.
`?extended=true` returns signatures, audio metadata, format details.

---

### **POST /cache/invalidate**

Invalidate a single stem.

Body:

```json
{ "stem_name": "stem.name.john" }
```

---

### **POST /cache/bulk_generate**

Batch generation based on datasets.

Body:

```json
{
  "names_path": "data/common_names.json",
  "developers_path": "data/developer_names.json"
}
```

---

### **GET /cache/check_in_bucket**

Check if stem exists in GCS.

---

### **GET /cache/bucket_list?prefix=...**

List items in the bucket.

---

### **NEW — GET /cache/check_many**

Bulk check many stems at once.

### **NEW — GET /cache/consistency_report**

Returns full comparison:

* match
* local_only
* gcs_only
* missing

### **NEW — POST /cache/verify_and_repair**

Auto-repairs missing stems by regenerating and syncing.

---

# **6. /external — Dataset Intake**

### **POST /external/upload_base**

Upload CSV/JSON/TXT containing names, developers, or custom lists.

Fields:

* file
* dataset_role
* target_name

---

### **POST /external/preview**

Preview dataset without saving.

---

### **GET /external/list**

List all datasets in `/data`.

---

### **DELETE /external/delete?filename=X**

Delete a dataset.

---

# **7. Diagnostics**

### **GET /health**

Basic readiness + Sonic-3 contract check.

### **GET /health/extended**

Adds GCS diagnostics and internal stats.

### **GET /live**

Liveness probe.

### **GET /ready**

Readiness probe.

### **GET /version**

Service version stamp.

---