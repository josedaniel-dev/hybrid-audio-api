# Hybrid Audio API — **Sonic-3 Internal Contract**

**Versión 5.3 — NDF-SAFE (Non-Destructive Fix Protocol)**
Documento Técnico Interno — Estándares obligatorios para compatibilidad total entre:
Backend · CLI · UI · Rotational Engine · Stems · Templates · GCS · Cartesia Sonic-3

---

## 1. Sonic-3 Payload Contract (Obligatorio)

Todos los requests al generador deben cumplir:

```
model_id: "sonic-3"
transcript: "<texto plano>"                # sin SSML, markup ni etiquetas
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

Requisitos adicionales:

* El `transcript` **solo puede ser texto plano**.
* El cliente debe enviar:

  * `X-Cartesia-Api-Key`
  * `X-Cartesia-Version`
* Se genera **WAV PCM S16LE 48 kHz mono**.

---

## 2. Naming Rules (Estándar Interno Obligatorio)

### **Stems**

Todos los stems deben seguir esta convención:

```
stem.name.<slug>.wav
stem.developer.<slug>.wav
stem.generic.<slug>.wav
silence.<duration>ms.wav
```

### **Outputs**

```
output.<name>.<developer>.<timestamp>.<merge_mode>.wav
```

* timestamp usa: `UTC → %Y%m%d_%H%M%S`
* `slug`:

  * minúsculas
  * espacios → `_`
  * caracteres inválidos → `_`

---

## 3. Template System (Contrato Estructural)

Un template válido **debe cumplir**:

```
{
  "template_name": "double_anchor_hybrid_v3_5",
  "segments": [
      { "id": "intro", "text": "Hola {first_name}", "break_ms": 100 },
      ...
  ],
  "placeholders": { ... }                # si existen
}
```

### Reglas estrictas:

* `segments` NO puede ser vacío.
* `id` debe ser único.
* `text` debe ser **texto plano**.
* Campos numéricos permitidos:

  * `gap_ms`
  * `crossfade_ms`
  * `break_ms`
  * `estimated_duration_ms`
    Todos ≥ **0**
* Silencios se materializan vía:

  ```
  silence.<n>ms.wav
  ```

---

## 4. Timing Rules

* `timing_map` es una lista de transiciones ordenadas.
* Cada transición referencia IDs válidos.
* `gap_ms`, `crossfade_ms`, `break_ms` ≥ 0.
* Silencios inexistentes se crean dinámicamente.
* El pipeline de timing garantiza:

  * nunca negativos
  * nunca NaN
  * silencios resueltos **antes** del merge
  * orden temporal estable

---

## 5. Stems y Outputs

### **Ubicación local**

```
stems/
output/
```

### **Validación WAV obligatoria**

TODOS los assets deben cumplir:

* PCM S16LE
* 48000 Hz
* mono
* tamaño > 0
* sin clipping
* sin NaN/Inf

### **Integrity checks**

Antes del merge:

* Escaneo de amplitud
* Escaneo de picos
* Normalización opcional (si el template lo exige)

---

## 6. Google Cloud Storage (Opcional / On-Demand)

Se activa cuando:

* bucket configurado
* credenciales disponibles

### Reglas:

* Los paths remotos reflejan exactamente los paths locales.
* `build_gcs_blob_path()` construye rutas internas.
* `build_gcs_uri()` construye URLs públicas o firmadas.
* Si el blob no existe, `gcs_uri = null`.

### **Consistency Engine**

* Compara:

  ```
  match
  local_only
  gcs_only
  missing
  ```

---

## 7. Error Model (Contratos de Excepción)

### Excepciones Sonic-3:

* `Sonic3Error` (base)
* `InvalidPayloadError`
* `VoiceIncompatibleError`
* `RateLimitError`

### Excepciones internas:

* `TemplateError`
* `TimingError`
* `BucketAccessError`
* `WavValidationError`
* `MergeIntegrityError`

Todas deben regresar:

```
{
  "error": "<type>",
  "message": "<details>",
  "hint": "<optional recovery hint>"
}
```

---

## 8. Regeneration Pipeline (Full Refresh)

Antes de regenerar:

1. **Eliminar stems legacy**
2. **Regenerar:**

   * names
   * developers
   * generic
   * silence stems
   * stems del template
3. **Escribir nuevo `stems_index.json`** con:

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

## 9. Extensión a UI / CLI / Tools

### Para cualquier componente externo:

* Usar **cartesia_client.build_payload()**
* Validar templates con `template_validator`
* Mostrar atributos WAV:

  * formato
  * duración
  * tamaño
  * timestamps
  * rutas
  * signed_urls (si existen)
* Respetar 100%:

  * naming rules
  * timing rules
  * payload contract
  * merge semantics

---

## 10. Garantía de Compatibilidad

Todo cambio futuro **debe ser NDF (No Destructivo)**:

* nunca renombrar stems existentes
* nunca alterar merges previos
* nunca romper rutas CLI/HTTP
* nunca modificar formatos de salida
* nunca cambiar la semántica de timestamps


