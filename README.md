
# 🎧 Hybrid Audio API — Sonic-3 Edition  
High-Performance Personalized Audio Generation · Cartesia TTS (2025)

Hybrid Audio API is a modular, contract-driven audio generation system that produces
dynamic, personalized voice messages by assembling reusable high-quality stems,
fully aligned with **Cartesia Sonic-3**.

The system supports:
- Real-time stem generation  
- Rotational datasets (names / developers)  
- Semantic timing assembly (bit-exact merge)  
- Full caching + regeneration  
- GCS upload  
- CLI + Makefile automation  
- Dataset ingestion (CSV/JSON)  

---

## 🚀 Core Features

### **🟦 Sonic-3 Contract Alignment**
All TTS calls follow the official 2025 API contract:
- `transcript` text
- voice via `"mode": "id"`
- 48 kHz WAV (`pcm_s16le`)
- deterministic stem naming  
- version header (`Cartesia-Version`)

### **🎙 Dynamic Stem Generation**
Routes for:
- `/generate/name`
- `/generate/developer`
- `/generate/combined`

Stems are cached locally with contract signatures:
- sample rate  
- encoding  
- voice_id  
- model_id  
- cartesia version  
- generation_config metadata  

### **🔁 Fair Rotational Engine**
Automatic cycling through datasets with:
- least-used priority  
- last_used timestamps  
- enable/disable flags  
- rotational metadata for stems  
- stats: used, unused, disabled, total coverage  

### **🔗 Semantic Assembly (bitmerge)**
- Bit-accurate float32 merging  
- Crossfades via cosine window  
- Optional timing_map  
- Clean merge fallback  
- Full output diagnostics (duration, RMS, clipping)

### **📦 GCS Integration**
- Upload stems  
- Upload outputs  
- Signed URLs  
- Bucket existence checks  
- Audits (size, metadata, presence)

### **📁 Dataset Ingestion**
Upload external CSV/JSON to build:
- common_names.json  
- developer_names.json  
- custom datasets  

### **🛡 Internal Security**
Optional header:
```

X-Internal-API-Key: <key>

```
Fail-open in DEV, strict in PROD.

### **📊 Observability**
- JSON logs
- request_id propagation
- timing ms metrics
- health + diagnostic endpoints

---

# 🧱 Project Structure

```

hybrid_audio_api/
├── assemble_message.py        # Sonic-3 generator + E2E assembly
├── batch_generate_stems.py    # rotational + template batch engine
├── bitmerge_semantic.py       # semantic timing bitmerge engine
├── cache_manager.py           # contract-aware stem index + cache
├── CLI.py                     # interactive CLI (HTTP orchestrator)
├── config.py                  # .env-driven configuration
├── gcloud_storage.py          # GCS client + upload tools
├── gcs_audit.py               # bucket audit utilities
├── audio_utils.py             # normalization + clean merge
├── rotational_engine.py       # dataset-aware rotation system
├── logging_utils.py           # JSON logs + request_id context
├── security.py                # internal API key validator
│
├── routes/
│   ├── assemble.py
│   ├── cache.py
│   ├── external.py
│   ├── generate.py
│   └── rotation.py
│
├── templates/
│   └── double_anchor_hybrid.json   # Sonic-3 aligned template
│
├── data/
│   ├── common_names.json
│   ├── developer_names.json
│   └── ... (custom datasets)
│
├── stems/                 # auto-generated stems (WAV)
├── output/                # merged final WAVs
├── logs/                  # JSON log stream
│
├── Makefile               # automation toolkit
└── fastapi_server.py      # API entrypoint

```

---

# ⚙️ API Overview

## **POST /generate/name**
Generate or fetch a cached name stem.

## **POST /generate/developer**
Same for developers.

## **POST /generate/combined**
Generates both stems in one call.

## **POST /assemble/template**
End-to-end personalized message using a JSON template.

## **POST /assemble/segments**
Manual assembly from arbitrary stems.

## **GET /generate/check/stem_in_bucket**
Verify existence of a stem in GCS.

## **GET /rotation/next**
Gets next name/developer pair via fair rotation.

## **GET /cache/list**
Full cache index, extended mode included.

## **POST /external/upload_base**
Upload CSV/JSON dataset and integrate it into the system.

---

# 🛠 CLI Usage

### Generate:
```

make cli ARGS="generate name John"
make cli ARGS="generate developer Hilton"
make cli ARGS="generate combined John Hilton --upload"

```

### Assemble:
```

make cli ARGS="assemble template John Hilton --template double_anchor_hybrid.json"

```

### Rotation:
```

make cli ARGS="rotation next"
make cli ARGS="rotation stats"

```

### Datasets:
```

make cli ARGS="external upload_base ./names.csv --target names"
make cli ARGS="external preview ./developers.json"

```

---

# 🏗 Makefile Highlights

### Start server:
```

make run

```

### Regenerate rotational stems:
```

make batch-rotations

```

### Regenerate template stems:
```

make batch-template

```

### Validate cache integrity:
```

make batch-validate

```

### Clean:
```

make clean

```

---

# 🧪 Template: double_anchor_hybrid.json

This is the default Sonic-3 ready template:
- No SSML  
- Deterministic segment IDs  
- Crossfade + gap config  
- Two variants (assertive, warm)  
- Metadata + duration estimate  

---

# ☁️ GCS Integration

The system can:
- upload stems  
- upload outputs  
- resolve blob URIs  
- produce signed URLs  
- verify bucket state  

---

# 🔒 Security

Use internal API key only for private routes:
```

export INTERNAL_API_KEY="your-key"

```

---

# 📘 Requirements

- Python 3.10+
- ffmpeg installed
- Cartesia API key
- Google Cloud service account (optional)

---

# 🧭 Vision

Hybrid Audio API provides a scalable, deterministic,
Sonic-3 aligned audio generation framework that enables
hyper-personalized outbound voice content using reusable stems,
semantic pacing, and modular templates.

---

# 🧩 License
MIT (for Hybrid_Audio). Cartesia TTS requires API key & usage rights.

---

