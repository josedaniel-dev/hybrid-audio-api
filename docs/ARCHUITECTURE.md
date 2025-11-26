# **Hybrid Audio API — Architectural Overview**

**Technical Architecture Report (v5.3)**
**Format:** Markdown
**Author:** Generated on request of the repository owner

---

## **1. Introduction**

Hybrid Audio API is a modular system designed to generate, assemble, and manage personalized audio using **Cartesia Sonic-3**, with strict technical contracts, advanced caching, and reproducible pipelines.
Its architecture integrates:

* Generation of personalized **voice stems** (name / developer / script)
* Hybrid assembly using **bitmerge_semantic** (bit-exact, no resampling)
* A **cache manager** that ensures full traceability of stems and outputs
* A **rotation engine** that provides deterministic cycling for datasets
* Optional **GCS** modules for remote consistency
* A **CLI** that operates entirely through HTTP without internal imports

The system follows **Non-Destructive Fix** principles: every improvement is additive, compatible, and traceable.

---

## **2. Global Project Structure**

```
hybrid_audio/
├── assemble_message.py
├── audio_utils.py
├── batch_generate_stems.py
├── bitmerge_semantic.py
├── cache_manager.py
├── CLI.py
├── config.py
├── fastapi_server.py
├── gcloud_storage.py
├── gcs_audit.py
├── gcs_consistency.py
├── logs/
├── output/
├── rotational_engine.py
├── routes/
│   ├── assemble.py
│   ├── cache.py
│   ├── generate.py
│   ├── rotation.py
│   └── external.py
├── stems/
├── templates/
└── tests/
```

---

## **3. Main Components**

### **3.1 FastAPI Server**

File: `fastapi_server.py`

* Central entry point

* Registers routers:

  * `/generate`
  * `/assemble`
  * `/rotation`
  * `/cache`
  * `/external`

* Runs with Uvicorn in development or production

---

## **4. Functional Modules**

### **4.1 Generation (Cartesia Sonic-3)**

Files:

* `generate.py` (router)
* `batch_generate_stems.py`
* `bitmerge_semantic.py`
* `audio_utils.py`

Key functions:

| Function                      | Purpose                                    |
| ----------------------------- | ------------------------------------------ |
| `generate_name()`             | Generates name stem                        |
| `generate_developer()`        | Generates developer stem                   |
| `generate_combined()`         | Generates both stems                       |
| `generate_rotational_stems()` | Batch generation (names × developers)      |
| `bitmerge_semantic()`         | Bit-exact concatenation without resampling |

The generation engine is fully contract-driven:

* Fixed format
* Fixed encoding
* Strict WAV validation

---

## **5. Assembly**

### File: `assemble_message.py`

Assembles full messages by combining stems:

* Uses JSON templates
* Cleans spacing, padding, and silence
* Produces outputs under `output/`

Assembly pipeline:

```
template_input
    → resolve stems
    → validate WAVs
    → bitmerge / hybrid merge
    → timestamped output
```

---

## **6. Cache System**

File: `cache_manager.py`
Router: `routes/cache.py`

Capabilities:

| Endpoint                 | Purpose                                |
| ------------------------ | -------------------------------------- |
| `/cache/list`            | Cache index and contract compatibility |
| `/cache/invalidate`      | Remove a specific stem                 |
| `/cache/bulk_generate`   | Generate stems for full datasets       |
| `/cache/check_in_bucket` | Compare local vs GCS                   |
| `/cache/bucket_list`     | List objects in the bucket             |

Cache index stores:

* audio_format
* encoding
* cartesia_version
* contract_signature
* timestamps
* local path

---

## **7. Rotation Engine**

File: `rotational_engine.py`
Router: `routes/rotation.py`

Provides deterministic rotation for:

* names
* developers
* scripts

Exposes:

* `/rotation/next_name`
* `/rotation/next_developer`
* `/rotation/next_pair`
* `/rotation/generate_pair`
* `/rotation/pairs_stream`
* `/rotation/next_script`
* `/rotation/scripts_stream`

Tracks state using timestamps and persistent metadata.

---

## **8. Google Cloud Storage Consistency**

Files:

* `gcloud_storage.py`
* `gcs_audit.py`
* `gcs_consistency.py`

Features:

| Module            | Purpose                                       |
| ----------------- | --------------------------------------------- |
| `gcloud_storage`  | Upload, exists, blob resolution               |
| `gcs_consistency` | Compare local and bucket directories          |
| `gcs_audit`       | Bucket listing and prefix-based introspection |

Two operating modes:

### **Local Mode**

No credentials. Local filesystem only.

### **GCS Mode**

Full remote consistency and auditing.

---

## **9. Global Configuration**

File: `config.py`

Includes:

* `BASE_DIR`
* `STEMS_DIR`
* `OUTPUT_DIR`
* `COMMON_NAMES_FILE`
* `DEVELOPER_NAMES_FILE`
* Structured path resolution:

  * `stem.name.john → stems/name/stem.name.john.wav`
  * `stem.developer.maria → stems/developer/stem.developer.maria.wav`
  * `stem.script.hello → stems/script/stem.script.hello.wav`

Environment variables include:

* `HYBRID_AUDIO_API_URL`
* `INTERNAL_API_KEY`
* `GCS_BUCKET`
* `CARTESIA_API_KEY`
* others

---

## **10. CLI (Command Line Interface)**

File: `CLI.py`

Features:

* Entirely HTTP-based

* Full command coverage

* Supports:

  * generate
  * assemble
  * rotation
  * cache
  * external

* Strong error handling

* Configurable timeouts

* Automatic name normalization

* Git-style subcommands

Examples:

```
make cli-generate ARGS="name Jose --extended"
make cli-assemble ARGS="template Jose Hilton --template double_anchor.json"
make cli-cache ARGS="list --extended"
```

---

## **11. Tests**

Directory: `tests/`

Covers:

| Test Suite             | Areas Tested                          |
| ---------------------- | ------------------------------------- |
| test_generate_*        | Stem generation and Sonic-3 contracts |
| test_assemble_*        | Template processing and bit-merge     |
| test_cache_*           | Cache system and signatures           |
| test_rotation_*        | Rotation cycles                       |
| test_script_stem_paths | Structured path resolution            |
| test_cli_*             | CLI compatibility                     |
| test_gcs_*             | GCS consistency (mocked)              |
| test_sonic3_*          | Sonic-3 payload contract compliance   |

Total: **30 tests**
Coverage: ~90%

---

## **12. Observability**

Directory: `logs/`

Contains audit logs for:

* CLI calls
* Rotation engine events
* Cache changes
* Batch jobs

Format: JSON Lines (JSONL)

---

## **13. Output and Storage Layout**

* `stems/` — all stems
* `output/` — assembled WAV messages
* `routes/` — router modules
* `logs/` — audit logs
* `data/` — base datasets

---

## **14. Conclusion**

Hybrid Audio API provides a modern, modular, contract-focused architecture with:

* Validated generation
* Deterministic assembly
* Secure caching
* Stable rotation
* Optional GCS integration
* Robust CLI
* Extensive testing

It is well-suited for production and can be extended with:

* new stem categories
* custom flows
* multi-tenant pipelines
* UI/UX integrations through the API
