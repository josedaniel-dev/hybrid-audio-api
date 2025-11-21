# ════════════════════════════════════════════════════════════
# Hybrid Audio API – Makefile v5.3 (Hardened / Sonic-3 Edition)
# Author: José Daniel Soto
# Secure GNU Make — No heredocs — No mixed indentation
# ════════════════════════════════════════════════════════════

SHELL := /bin/bash
.SHELLFLAGS := -eu -o pipefail -c

PYTHON := python3
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate
HOST := 127.0.0.1
PORT := 8000
CLI := $(PYTHON) CLI.py
ARGS ?=

ENV_FILE := .env
INTERNAL_API_KEY := $(shell grep -E '^INTERNAL_API_KEY=' $(ENV_FILE) 2>/dev/null | cut -d= -f2-)

# ════════════════════════════════════════════════════════════
# ENVIRONMENT
# ════════════════════════════════════════════════════════════

check-env-file:
	@if [ ! -f "$(ENV_FILE)" ]; then \
		echo "❌ ERROR: Missing .env file."; \
		echo "   Crea un .env basado en .env.template antes de continuar."; \
		exit 1; \
	fi

check-prod-key:
	@if [ "$${MODE:-DEV}" = "PROD" ] && [ -z "$(INTERNAL_API_KEY)" ]; then \
		echo "❌ ERROR: INTERNAL_API_KEY requerido en modo PROD."; \
		exit 1; \
	fi

init-folders:
	mkdir -p stems output data logs templates routes observability tests

env-check: check-env-file
	@echo "🧩 Verificando entorno virtual…"
	@if [ ! -d "$(VENV)/bin" ]; then \
		echo "⚙️ Creando entorno virtual (.venv)…"; \
		$(PYTHON) -m venv $(VENV); \
		$(ACTIVATE) && pip install --upgrade pip setuptools wheel; \
		if [ -f requirements.txt ]; then \
			$(ACTIVATE) && pip install -r requirements.txt; \
		else \
			echo "⚠️ WARNING: no se encontró requirements.txt"; \
		fi; \
	else \
		echo "✅ Entorno virtual OK."; \
	fi

init: env-check init-folders check-prod-key
	@echo "✨ Entorno inicializado y listo."

# ════════════════════════════════════════════════════════════
# SERVER
# ════════════════════════════════════════════════════════════

run: check-env-file check-prod-key env-check
	@echo "🌐 Lanzando Hybrid Audio API en modo desarrollo (auto-reload)…"
	@$(ACTIVATE) && uvicorn fastapi_server:app --reload --host 0.0.0.0 --port $(PORT)

run-prod: check-env-file check-prod-key env-check
	@echo "🚀 Lanzando Hybrid Audio API en modo PRODUCCIÓN…"
	@$(ACTIVATE) && uvicorn fastapi_server:app --host 0.0.0.0 --port $(PORT)

restart:
	@echo "🔁 Reiniciando servidor uvicorn…"
	@pkill -f "uvicorn" || true
	@sleep 1
	@$(MAKE) run

# ════════════════════════════════════════════════════════════
# CLI WRAPPERS
# ════════════════════════════════════════════════════════════

cli:
	@$(ACTIVATE) && $(CLI) $(ARGS)

cli-generate:
	@$(ACTIVATE) && $(CLI) generate $(ARGS)

cli-assemble:
	@$(ACTIVATE) && $(CLI) assemble $(ARGS)

cli-rotation:
	@$(ACTIVATE) && $(CLI) rotation $(ARGS)

cli-cache:
	@$(ACTIVATE) && $(CLI) cache $(ARGS)

cli-external:
	@$(ACTIVATE) && $(CLI) external $(ARGS)

# ════════════════════════════════════════════════════════════
# NEW — FASE 5 (Aditivo, no destructivo)
# ════════════════════════════════════════════════════════════

cli-rotation-scripts:
	@$(ACTIVATE) && $(CLI) rotation next_script || true
	@$(ACTIVATE) && $(CLI) rotation generate_script --extended || true
	@$(ACTIVATE) && $(CLI) rotation scripts_stream --limit 10 || true

cli-cache-check-bucket:
	@$(ACTIVATE) && $(CLI) cache check_in_bucket $(ARGS)

cli-bucket-list:
	@$(ACTIVATE) && $(CLI) cache bucket_list $(ARGS)

# ════════════════════════════════════════════════════════════
# BATCH GENERATION
# ════════════════════════════════════════════════════════════

batch-rotations: env-check
	@echo "🔁 Generando stems de rotación (names + developers)…"
	@$(ACTIVATE) && $(PYTHON) -c \
	"from pathlib import Path; from batch_generate_stems import generate_rotational_stems; \
	generate_rotational_stems(Path('data/common_names.json'), Path('data/developer_names.json'))"
	@echo "✅ Rotational batch completo (stems en carpeta stems/)."

batch-template: env-check
	@echo "📜 Generando stems desde template base (double_anchor_hybrid_v3_5)…"
	@$(ACTIVATE) && $(PYTHON) -c \
	"from batch_generate_stems import generate_from_template; \
	generate_from_template('templates/double_anchor_hybrid_v3_5.json', first_name='John', developer='Hilton', max_workers=4)"
	@echo "✅ Template stems generados."

batch-outputs: env-check
	@echo "🎧 Ensamblando TODOS los outputs (todas las combinaciones name x developer)…"
	@$(ACTIVATE) && $(PYTHON) -c \
	"import json; from itertools import product; \
	from config import BASE_DIR; from assemble_message import assemble_pipeline; \
	with open(BASE_DIR/'data/common_names.json') as f1, open(BASE_DIR/'data/developer_names.json') as f2: \
	 names=json.load(f1)['items']; devs=json.load(f2)['items']; \
	[assemble_pipeline(n, d, clean_merge=True, template_name='double_anchor_hybrid_v3_5.json') for n,d in product(names, devs)]"
	@echo "✅ Batch outputs completos (WAVs en output/)."

# ════════════════════════════════════════════════════════════
# AUDITS / ROTATION STATUS
# ════════════════════════════════════════════════════════════

rotation-stats: env-check
	@echo "📊 Estadísticas del rotational engine…"
	@$(ACTIVATE) && $(PYTHON) -c \
	"import json; from rotational_engine import rotation_stats; \
	print(json.dumps(rotation_stats(), indent=2, ensure_ascii=False))"

# ════════════════════════════════════════════════════════════
# TESTING (HTTP + pytest)
# ════════════════════════════════════════════════════════════

_curl = curl -fSs -H "X-Internal-API-Key: $(INTERNAL_API_KEY)"

test-template:
	@echo "🧪 Test rápido: /assemble/template (plantilla principal)…"
	@$(ACTIVATE) && $(_curl) -X POST \
	"http://$(HOST):$(PORT)/assemble/template?extended=true" \
	-H "Content-Type: application/json" \
	-d '{"first_name":"John","developer":"Hilton","template":"double_anchor_hybrid_v3_5.json","upload":false}' | jq .

test-cache-list:
	@echo "🧪 Test rápido: /cache/list (estado de cache)…"
	@$(ACTIVATE) && $(_curl) "http://$(HOST):$(PORT)/cache/list?extended=true" | jq .

pytest:
	@echo "🧪 Ejecutando suite pytest completa (máx 1 fallo)…"
	@$(ACTIVATE) && pytest -q --disable-warnings --maxfail=1

# ════════════════════════════════════════════════════════════
# VALIDACIÓN MANUAL GUIADA (NEW)
# ════════════════════════════════════════════════════════════

validate-manual: env-check
	@echo "🔎 Validación manual básica de Hybrid Audio API (CLI + API)…"
	@echo "  1) Verificando que el servidor responde en /docs…"
	@$(ACTIVATE) && curl -sSf "http://$(HOST):$(PORT)/docs" >/dev/null || { \
		echo "❌ No se pudo acceder a http://$(HOST):$(PORT)/docs. Asegúrate de ejecutar 'make run' en otra terminal."; \
		exit 1; \
	}
	@echo "  2) Generando un stem por nombre…"
	@$(ACTIVATE) && $(CLI) generate name "Jose" --extended || { echo "❌ Falló generate name"; exit 1; }
	@echo "  3) Generando un stem por developer…"
	@$(ACTIVATE) && $(CLI) generate developer "Hilton" --extended || { echo "❌ Falló generate developer"; exit 1; }
	@echo "  4) Generando un combinado name+developer…"
	@$(ACTIVATE) && $(CLI) generate combined "Jose" "Hilton" --extended || { echo "❌ Falló generate combined"; exit 1; }
	@echo "  5) Ensamblando mensaje desde template (double_anchor_hybrid_v3_5)…"
	@$(ACTIVATE) && $(CLI) assemble template "Jose" "Hilton" --template "double_anchor_hybrid_v3_5.json" --extended || { echo "❌ Falló assemble template"; exit 1; }
	@echo "  6) Consultando ubicación de output…"
	@$(ACTIVATE) && $(CLI) assemble output_location || { echo "❌ Falló output_location"; exit 1; }
	@echo "  7) Probando rotation stream (primeros 5 pares)…"
	@$(ACTIVATE) && $(CLI) rotation stream --limit 5 || { echo "❌ Falló rotation stream"; exit 1; }
	@echo "  8) Listando cache actual…"
	@$(ACTIVATE) && $(CLI) cache list --extended || { echo "❌ Falló cache list"; exit 1; }
	@echo "✅ Validación manual básica completada. Revisa los JSON impresos arriba."

# ════════════════════════════════════════════════════════════
# FULL BATCH PIPELINE (NEW)
# ════════════════════════════════════════════════════════════

full-batch: env-check
	@echo "🚚 FULL BATCH: cache bulk + outputs masivos."
	@echo "  1) Generando cache masivo (names + developers) vía /cache/bulk_generate…"
	@$(ACTIVATE) && $(CLI) cache bulk || { echo "❌ Falló cache bulk"; exit 1; }
	@echo "  2) Ensamblando todos los outputs (todas las combinaciones name x developer)…"
	@$(MAKE) batch-outputs
	@echo "✅ FULL BATCH completado."
	@echo "   → Stems en:   stems/"
	@echo "   → Outputs en: output/"
	@echo "   Si deseas un solo archivo concatenado, puedes usar por ejemplo:"
	@echo "     sox output/*.wav output/final_compilation.wav"
	@echo "   (requiere sox instalado en el sistema)."

# ════════════════════════════════════════════════════════════
# CLEANUP
# ════════════════════════════════════════════════════════════

clean:
	@echo "🧹 Limpiando artefactos…"
	@find . -type d -name "__pycache__" -exec rm -rf {} +
	@find output -type f -name "*.wav" -delete
	@echo "✅ Cleanup completo (WAVs y __pycache__ eliminados)."

# ════════════════════════════════════════════════════════════
# HELP — EXPANDIDO (TODOS LOS COMANDOS)
# ════════════════════════════════════════════════════════════

help:
	@echo ""
	@echo "═══════════════════════════════════════════"
	@echo " Hybrid Audio API – Makefile HELP (v5.3)"
	@echo "═══════════════════════════════════════════"
	@echo ""
	@echo "🧱 ENTORNO:"
	@echo "  make init                → Crea/actualiza .venv, instala deps y crea carpetas base."
	@echo "  make env-check           → Verifica que exista .env y que el entorno virtual esté listo."
	@echo ""
	@echo "🌐 SERVIDOR API:"
	@echo "  make run                 → Levanta FastAPI en modo DEV con auto-reload (0.0.0.0:8000)."
	@echo "  make run-prod            → Levanta FastAPI en modo PROD (sin auto-reload)."
	@echo "  make restart             → Mata procesos uvicorn y vuelve a ejecutar 'make run'."
	@echo ""
	@echo "🖥️ CLI (WRAPPER GENERAL):"
	@echo "  make cli ARGS='...'      → Ejecuta CLI.py con ARGS crudos."
	@echo ""
	@echo "🎧 CLI – GENERATE:"
	@echo "  make cli-generate ARGS=\"name <Nombre> [--voice_id ID] [--extended]\""
	@echo "  make cli-generate ARGS=\"developer <Developer> [--voice_id ID] [--extended]\""
	@echo "  make cli-generate ARGS=\"combined <Nombre> <Developer> [--voice_id ID] [--extended]\""
	@echo ""
	@echo "🎼 CLI – ASSEMBLE:"
	@echo "  make cli-assemble ARGS=\"template <Nombre> <Developer> --template T.json [--upload] [--extended]\""
	@echo "  make cli-assemble ARGS=\"raw stem1.wav stem2.wav ... [--upload]\""
	@echo "  make cli-assemble ARGS=\"output_location\""
	@echo ""
	@echo "🔁 CLI – ROTATION:"
	@echo "  make cli-rotation ARGS=\"next_name\""
	@echo "  make cli-rotation ARGS=\"next_developer\""
	@echo "  make cli-rotation ARGS=\"next_pair\""
	@echo "  make cli-rotation ARGS=\"generate_pair [--voice_id ID] [--extended]\""
	@echo "  make cli-rotation ARGS=\"stream --limit N\""
	@echo ""
	@echo "📝 CLI – ROTATION SCRIPTS (NEW):"
	@echo "  make cli-rotation-scripts"
	@echo ""
	@echo "🗄️ CLI – CACHE:"
	@echo "  make cli-cache ARGS=\"list [--extended]\""
	@echo "  make cli-cache ARGS=\"invalidate <stem_name>\""
	@echo "  make cli-cache ARGS=\"bulk [--names json] [--developers json]\""
	@echo "  make cli-cache-check-bucket ARGS=\"--label stem.name.jose\" (NEW)"
	@echo "  make cli-bucket-list ARGS=\"--prefix stems/name\" (NEW)"
	@echo ""
	@echo "📂 CLI – EXTERNAL DATASETS:"
	@echo "  make cli-external ARGS=\"upload ruta.ext --role names|developers|custom [--target clave]\""
	@echo "  make cli-external ARGS=\"preview ruta.ext\""
	@echo ""
	@echo "📦 BATCH:"
	@echo "  make batch-rotations"
	@echo "  make batch-template"
	@echo "  make batch-outputs"
	@echo ""
	@echo "📊 AUDITORÍA:"
	@echo "  make rotation-stats"
	@echo ""
	@echo "🧪 TESTING:"
	@echo "  make test-template"
	@echo "  make test-cache-list"
	@echo "  make pytest"
	@echo ""
	@echo "🔎 VALIDACIÓN:"
	@echo "  make validate-manual"
	@echo ""
	@echo "🚚 FULL BATCH:"
	@echo "  make full-batch"
	@echo ""
	@echo "🧹 CLEAN:"
	@echo "  make clean"
	@echo ""
	@echo "═══════════════════════════════════════════"
	@echo " END HELP"
	@echo "═══════════════════════════════════════════"
