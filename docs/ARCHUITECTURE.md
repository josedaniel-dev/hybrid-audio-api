# Hybrid Audio API — Architectural Overview

**Technical Architecture Report (v5.3)**
**Formato:** Markdown
**Autor:** Generado bajo solicitud del propietario del repositorio

---

## 1. Introducción

Hybrid Audio API es un sistema modular diseñado para generar, ensamblar y administrar audio personalizado basado en **Cartesia Sonic-3**, usando un modelo estricto de contratos técnicos, caching avanzado y pipelines reproducibles.
El sistema combina:

* Generación de **stems** de voz personalizados (name / developer / script).
* Ensamblaje híbrido mediante **bitmerge_semantic** (join exacto sin resampleo).
* Un **cache manager** que garantiza trazabilidad de todos los stems y outputs.
* Un **rotation engine** que administra ciclos determinísticos de nombres y developers.
* Módulos opcionales de **GCS** (Google Cloud Storage) para consistencia remota.
* Un **CLI** robusto que invoca directamente a las rutas HTTP, sin dependencias internas.

La arquitectura está diseñada siguiendo los principios **NDF (Non-Destructive Fix)**:
cada mejora es aditiva, no destructiva, manteniendo compatibilidad y trazabilidad.

---

## 2. Estructura Global del Proyecto

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

## 3. Componentes Principales

### 3.1 **FastAPI Server**

Archivo: `fastapi_server.py`

* Punto de entrada del API.
* Incluye routers:

  * `/generate`
  * `/assemble`
  * `/rotation`
  * `/cache`
  * `/external`
* Usa Uvicorn en local o producción.

---

## 4. Módulos Funcionales

### 4.1 Generación (Cartesia Sonic-3)

Archivos:

* `generate.py` (router)
* `batch_generate_stems.py`
* `bitmerge_semantic.py`
* `audio_utils.py`

Funciones clave:

| Función                       | Propósito                                   |
| ----------------------------- | ------------------------------------------- |
| `generate_name()`             | Genera stem para primer nombre.             |
| `generate_developer()`        | Genera stem para developer.                 |
| `generate_combined()`         | Genera ambos sin repeticiones.              |
| `generate_rotational_stems()` | Genera datasets completos name × developer. |
| `bitmerge_semantic()`         | Concatena audio de forma bit-exact.         |

El motor de generación es contract-driven:

* Formato fijo
* Encoding fijo
* Validación WAV estricta

---

## 5. Ensamblaje

### Archivo: `assemble_message.py`

Realiza el “mensaje completo” combinando stems:

* Usa templates JSON (`templates/*.json`)
* Limpia espacios, pads y silencios
* Produce outputs en `output/`

Pipeline:

```
template_input
    → resolve stems
    → validate WAVs
    → bitmerge/hybrid merge
    → timestamped output
```

---

## 6. Cache System

Archivo: `cache_manager.py`
Router: `routes/cache.py`

Funcionalidades:

| Endpoint                 | Descripción                                           |
| ------------------------ | ----------------------------------------------------- |
| `/cache/list`            | Estado total del cache + compatibilidad de contratos. |
| `/cache/invalidate`      | Remueve un stem específico.                           |
| `/cache/bulk_generate`   | Genera stems para todos los nombres y developers.     |
| `/cache/check_in_bucket` | Verifica consistencia local vs GCS.                   |
| `/cache/bucket_list`     | Lista contenidos de bucket remoto.                    |

El index del cache contiene:

* audio_format
* encoding
* cartesia_version
* contract_signature
* timestamps
* local path

---

## 7. Rotation Engine

Archivo: `rotational_engine.py`
Router: `routes/rotation.py`

Roles:

* Iteración determinística sobre:

  * Nombres
  * Developers
  * Scripts
* Proporciona:

  * `/rotation/next_name`
  * `/rotation/next_developer`
  * `/rotation/next_pair`
  * `/rotation/generate_pair`
  * `/rotation/pairs_stream`
  * `/rotation/scripts_stream`
  * `/rotation/next_script`

Mantiene estado con timestamps y logs rotativos.

---

## 8. Consistencia con Google Cloud Storage (GCS)

Archivos:

* `gcloud_storage.py`
* `gcs_audit.py`
* `gcs_consistency.py`

Características:

| Módulo            | Función                                                |
| ----------------- | ------------------------------------------------------ |
| `gcloud_storage`  | CRUD sobre objetos (upload, exists, resolve).          |
| `gcs_consistency` | Compare local vs bucket, detectar faltantes/desfase.   |
| `gcs_audit`       | Listado de bucket por prefix (stems, name/, script/…). |

El sistema soporta dos modos:

### Modo Local

No requiere credenciales.
Verifica solo filesystem local.

### Modo GCS

Usa credenciales activas.
Permite auditoría completa.

---

## 9. Configuración Global

Archivo: `config.py`

Incluye:

* `BASE_DIR`
* `STEMS_DIR`
* `OUTPUT_DIR`
* `COMMON_NAMES_FILE`
* `DEVELOPER_NAMES_FILE`
* Resolución dinámica de rutas:

  * `stem.name.john → stems/name/stem.name.john.wav`
  * `stem.developer.maria → stems/developer/stem.developer.maria.wav`
  * `stem.script.hello → stems/script/stem.script.hello.wav`

También incluye variables de entorno:

* `HYBRID_AUDIO_API_URL`
* `INTERNAL_API_KEY`
* `GCS_BUCKET`
* `CARTESIA_API_KEY`
* Entre otras.

---

## 10. CLI (Command Line Interface)

Archivo: `CLI.py`

Características:

* **100% HTTP**, sin imports internos
* Todas las rutas están expuestas
* Soporta:

  * generate
  * assemble
  * rotation
  * cache
  * external datasets
* Control de errores robusto
* Timeouts configurables
* Autenticación por header interno
* Normalización automática de nombres
* Uso de sub-comandos estilo git

Ejemplo:

```
make cli-generate ARGS="name Jose --extended"
make cli-assemble ARGS="template Jose Hilton --template double_anchor.json"
make cli-cache ARGS="list --extended"
```

---

## 11. Tests

Carpeta: `tests/`

Incluye:

| Test Suite             | Cubre                                    |
| ---------------------- | ---------------------------------------- |
| test_generate_*        | Generación de stems y contratos Cartesia |
| test_assemble_*        | Ensamblaje exacto, bitmerge              |
| test_cache_*           | Cache manager, firmas, index             |
| test_rotation_*        | Ciclos determinísticos                   |
| test_script_stem_paths | Resolución estructurada                  |
| test_cli_*             | Compatibilidad del CLI                   |
| test_gcs_*             | Integración/mocks de GCS                 |
| test_sonic3_*          | Validación de contratos Sonic-3          |

Total: **30 tests**
Garantizado: **90% del sistema funcional**
Altamente modular y fácil de extender.

---

## 12. Observabilidad

Carpeta: `logs/`

* Registra:

  * llamadas del CLI
  * operaciones del rotation engine
  * auditorías de cache
  * batch jobs completos

Formato: JSON lineal (JSONL)

---

## 13. Output & Storage

* **stems/** contiene los stems generados
* **output/** contiene mensajes ensamblados
* **routes** divide responsabilidades por módulo
* **logs/** registra auditoría
* **data/** almacena datasets base (names/developers)

---

# 14. Conclusión

Hybrid Audio API posee una arquitectura moderna, modular, auditada y alineada con un contrato técnico estricto.
Sus componentes forman un pipeline completamente reproducible, con:

✔ Generación validada
✔ Ensamblaje determinístico
✔ Cache seguro
✔ Rotación estable
✔ Integración opcional con GCS
✔ CLI robusto
✔ Testing exhaustivo

Es una base sólida para uso en producción y permite extender:

* nuevos tipos de stems
* flujos personalizados
* pipelines multi-tenant
* UI/UX integradas vía API

