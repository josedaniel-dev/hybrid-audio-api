Perfecto.
Aquí tienes el **README.md profesional, limpio, versión A**, totalmente coherente con Hybrid Audio API v5.3, sin extras, sin adornos, sin menciones innecesarias.

---

# Hybrid Audio API — v5.3 (Sonic-3 Edition)

Microservicio modular para generación, ensamblaje y administración de audio personalizado usando **Cartesia Sonic-3**, con énfasis en reproducibilidad, contratos técnicos estrictos y escalabilidad.

---

## 1. Características Principales

### Generación de stems (Sonic-3)

* `/generate/name`
* `/generate/developer`
* `/generate/combined`
* Validación WAV
* Manejo completo de voice_id
* Payload alineado con `/tts/bytes`

### Ensamblaje profesional

* `/assemble/template`
* `/assemble/segments`
* `/assemble/output_location`
* Merges bit-exact sin resample
* Templates JSON versionados

### Motor de rotación

* Soporte para nombres, developers y scripts
* Ciclos determinísticos sin repeticiones
* Generación de pares y streams configurables
* Estado persistente en disco

### Cache Manager

* Índice contract-aware
* Firma de contrato Sonic-3
* Compatibilidad automática
* Bulk generation
* Invalidación segura
* Resumen extendido

### Integración GCS (opcional)

* Verificación local ↔ remota
* Listado del bucket
* Comparación por categorías
* Resolución estructurada de paths
* Fallback limpio cuando GCS está desactivado

### CLI 100% HTTP

* Sin imports internos
* Soporte para todas las rutas principales
* Upload de datasets externos
* Validaciones automáticas

### Test suite completa

* Generación
* Ensamblaje
* Cache
* Rotación
* GCS mockeado
* CLI
* End-to-end mínimo
* Validación Sonic-3

---

## 2. Estructura del Proyecto

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
├── gcs_events.py
├── rotational_engine.py
├── routes/
│   ├── assemble.py
│   ├── cache.py
│   ├── generate.py
│   ├── rotation.py
│   └── external.py
├── stems/
├── templates/
├── data/
├── logs/
└── tests/
```

---

## 3. Instalación

Requisitos:

* Python 3.12+
* ffmpeg
* sox (opcional)
* Cuenta Cartesia + API key
* Credenciales GCS (si aplica)

Inicializar entorno:

```
make init
```

---

## 4. Ejecución del Servidor

### Desarrollo

```
make run
```

### Producción

```
make run-prod
```

---

## 5. Uso del CLI

### Generación

```
make cli-generate ARGS="name Jose"
make cli-generate ARGS="developer Hilton"
make cli-generate ARGS="combined Jose Hilton"
```

### Ensamblaje

```
make cli-assemble ARGS="template Jose Hilton --template double_anchor_hybrid_v3_5.json"
```

### Rotación

```
make cli-rotation ARGS="next_pair"
make cli-rotation ARGS="generate_pair"
make cli-rotation ARGS="stream --limit 10"
```

### Cache

```
make cli-cache ARGS="list"
make cli-cache ARGS="invalidate stem.name.Jose"
make cli-cache ARGS="bulk"
```

### GCS

```
make cli-cache-check-bucket ARGS="--label stem.name.jose"
make cli-bucket-list ARGS="--prefix stems/name"
```

### Datasets externos

```
make cli-external ARGS="upload data/my.csv --role names"
```

---

## 6. Principales Rutas HTTP

### /generate

* `POST /generate/name`
* `POST /generate/developer`
* `POST /generate/combined`

### /assemble

* `POST /assemble/template`
* `POST /assemble/segments`
* `GET  /assemble/output_location`

### /rotation

* `GET  /rotation/next_name`
* `GET  /rotation/next_developer`
* `GET  /rotation/next_pair`
* `POST /rotation/generate_pair`
* `GET  /rotation/pairs_stream`
* `GET  /rotation/next_script`
* `POST /rotation/generate_script`
* `GET  /rotation/scripts_stream`

### /cache

* `GET  /cache/list`
* `POST /cache/invalidate`
* `POST /cache/bulk_generate`
* `GET  /cache/check_in_bucket`
* `GET  /cache/bucket_list`
* `GET  /cache/check_many`
* `GET  /cache/consistency_report`
* `POST /cache/verify_and_repair`

### /external

* `POST /external/upload_base`
* `POST /external/preview`
* `GET  /external/list`
* `DELETE /external/delete`

---

## 7. Pipeline de Ensamblaje

1. Parse de template
2. Resolución de stems (estructura name/developer/script)
3. Validación WAV
4. Bit-merge exacto
5. Output final en `output/`

Garantías:

* Preserva samplerate
* Preserva bit depth
* Sin resample
* Sin clipping

---

## 8. Pipeline de Rotación

1. Carga de datasets
2. Selección determinística
3. Estado persistente
4. Streams
5. Integración con generación Sonic-3

---

## 9. Integración con GCS

Capacidades:

* Verificación remota
* Listados por prefix
* Comparador de categorías
* Sincronización incremental
* Healthcheck interno

---

## 10. Tests

Ejecutar:

```
make pytest
```

Cubre:

* Merges
* WAV validation
* Rotación
* Cache signatures
* GCS mock
* CLI
* End-to-end
* Plantillas
* Contrato Sonic-3

---

## 11. Logs y Auditoría

Generados en:

```
logs/*.jsonl
```

Incluyen:

* Operaciones GCS
* Auditorías de stems
* Eventos de rotación
* Estado del pipeline

---

## 12. Full Batch Pipeline

```
make full-batch
```

Genera:

* Stems masivos
* Outputs masivos
* Combinaciones name × developer

---

## 13. Licencia

MIT License.

Desarrollado por **José Daniel Soto**.
