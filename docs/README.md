# Hybrid Audio API — v5.3 (Sonic-3 Edition)

**Audio Personalization Engine · Contract-Driven · Fully Tested**

Hybrid Audio API es un sistema modular diseñado para generar, ensamblar y administrar audio personalizado utilizando **Cartesia Sonic-3**, con un énfasis extremo en:

* **Contratos técnicos inmutables**
* **Reproducibilidad completa**
* **Merges bit-exact**
* **Cache inteligente y auditable**
* **Pipelines escalables**
* **Integración opcional con Google Cloud Storage (GCS)**
* **Rotación determinística de nombres, developers y scripts**
* **CLI totalmente HTTP (sin imports internos)**
* **Test suite automatizada con 30 pruebas unitarias**

La arquitectura completa sigue el estándar **NDF — Non-Destructive Fix Protocol**, garantizando que cada cambio sea aditivo, reversible y trazable.

---

# 1. Características Principales

### 🔊 Generación de stems con Sonic-3

* `/generate/name`
* `/generate/developer`
* `/generate/combined`
* Modo extendido para depuración
* Manejo de voice_id
* Validación WAV estricta

### 🎼 Ensamblaje profesional

* `/assemble/template`
* `/assemble/segments`
* `/assemble/output_location`
* Merge exacto sin alteración de samplerate ni bit depth
* Templates JSON versionados

### 🔁 Rotational Engine

* Nombres
* Developers
* Scripts
* Generación de pares
* Streams con límite
* Estado persistente y auditable

### 🗄️ Cache Manager

* Cache index contract-aware
* Firma de contrato Sonic-3
* Listados extendidos
* Invalidación segura
* Bulk generation
* Auditorías completas

### ☁️ Integración opcional con GCS

* Verificación local → bucket
* Listado remoto
* Resolución estructurada de stems
* Comparación por categorías
* GCS desactivado → fallback limpio

### 🧪 Test suite completa

30 tests cubriendo:

* Generación
* Ensamblaje
* Merges
* Cache
* Rotational
* Rutas
* CLI
* GCS mocked
* Contratos Sonic-3

---

# 2. Estructura del Proyecto

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

# 3. Instalación

## Requisitos

* Python 3.12+
* ffmpeg
* sox (opcional para concatenaciones masivas)
* Cuenta de Cartesia + API key (opcional para SONIC-3)
* Credenciales GCS (si se usa bucket remoto)

---

# 4. Inicialización

```
make init
```

Crea:

* `.venv/`
* carpetas base
* instala dependencias
* valida `.env`

---

# 5. Ejecución del Servidor

### Modo desarrollo

```
make run
```

### Modo producción

```
make run-prod
```

---

# 6. Uso del CLI (HTTP-first)

Todos los comandos llaman rutas reales del backend.
Ejemplos:

### Generar stem

```
make cli-generate ARGS="name Jose --extended"
make cli-generate ARGS="developer Hilton"
make cli-generate ARGS="combined Jose Hilton"
```

### Ensamblar mensaje

```
make cli-assemble ARGS="template Jose Hilton --template double_anchor_hybrid_v3_5.json --extended"
```

### Rotación

```
make cli-rotation ARGS="next_pair"
make cli-rotation ARGS="generate_pair --extended"
make cli-rotation ARGS="stream --limit 10"
```

### Cache

```
make cli-cache ARGS="list --extended"
make cli-cache ARGS="invalidate stem.name.Jose"
make cli-cache ARGS="bulk"
```

### External datasets

```
make cli-external ARGS="upload data/myfile.csv --role names --target custom_names"
```

---

# 7. Rutas HTTP Principales

### /generate/*

* `POST /generate/name`
* `POST /generate/developer`
* `POST /generate/combined`

### /assemble/*

* `POST /assemble/template`
* `POST /assemble/segments`
* `GET /assemble/output_location`

### /rotation/*

* `GET /rotation/next_name`
* `GET /rotation/next_developer`
* `GET /rotation/next_pair`
* `POST /rotation/generate_pair`
* `GET /rotation/pairs_stream`
* (v5.2+) `/rotation/next_script`, `/rotation/generate_script`, `/rotation/scripts_stream`

### /cache/*

* `GET /cache/list`
* `POST /cache/invalidate`
* `POST /cache/bulk_generate`
* `GET /cache/check_in_bucket`
* `GET /cache/bucket_list`

### /external/*

* `POST /external/upload_base`
* `POST /external/preview`
* `GET /external/list`
* `DELETE /external/delete`

---

# 8. Pipeline de Ensamblaje

```
template.json
     ↓ parsing
resolve stems
     ↓ validate WAV
bitmerge_semantic()
     ↓ timestamped output
output/final.wav
```

Garantías:

* samplerate preservado
* bit depth preservado
* no resample
* no clipping
* merge tiempo-exacto

---

# 9. Pipeline de Rotación

```
names.json
developers.json
scripts.json
     ↓ rotation cycles
rotation_stats()
     ↓
/rotation/next_pair
/rotation/generate_pair
```

El sistema garantiza:

* Sin repeticiones hasta completar ciclo
* Estado persistente en logs
* Streams configurables

---

# 10. Integración con Google Cloud Storage

### Modos

1. **Local only**
2. **Full remote consistency**

### Capacidades

* Listar bucket (`/cache/bucket_list`)
* Verificar existencia remota (`/cache/check_in_bucket`)
* Comparación:

  * local_only
  * gcs_only
  * match
  * missing

---

# 11. Tests

Ejecutar:

```
make pytest
```

Tests incluidos:

* Bitmerge
* WAV validation
* Rotation engine
* Cache signatures
* GCS mocked operations
* Template assembly
* CLI invocation
* End-to-end minimal
* Sonic-3 contract validation

---

# 12. Logs y Observabilidad

Logs generados en:

```
logs/*.jsonl
```

Incluyen:

* Operaciones del CLI
* Rotational engine
* Cache updates
* Auditorías GCS

---

# 13. Full Batch Pipeline

```
make full-batch
```

Produce:

* stems masivos (name × developer)
* outputs masivos (WAV)
* pipeline reproducible completo

---

# 14. LICENSE

MIT License.

---

# 15. Créditos

Desarrollado como parte del proyecto **Hybrid Audio API / Sonic-3 Engine** por *José Daniel Soto*.

