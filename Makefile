# Hybrid Audio API – Makefile v5.1 (Sonic-3 / Routers Edition)
# Author: José Daniel Soto
# GNU Make Safe · No heredocs · No mixed indents

SHELL := /bin/bash
PYTHON := python3
VENV := .venv
ACTIVATE := . $(VENV)/bin/activate
HOST := 127.0.0.1
PORT := 8000
CLI := $(PYTHON) CLI.py
ARGS ?=

# ─────────────────────────────────────────────
# SECTION 0 — ENVIRONMENT
# ─────────────────────────────────────────────

init-folders:
	mkdir -p stems output data logs templates routes observability

env-check:
	@echo "🧩 Checking virtual environment..."
	@if [ ! -d "$(VENV)/bin" ]; then \
		echo "⚙️ Creating virtual environment..."; \
		$(PYTHON) -m venv $(VENV); \
		$(ACTIVATE) && pip install --upgrade pip setuptools wheel; \
		$(ACTIVATE) && pip install -r requirements.txt; \
	else \
		echo "✅ Environment OK."; \
	fi

init: env-check init-folders
	@echo "Environment + folder structure ready."

# ─────────────────────────────────────────────
# SECTION 1 — SERVER / API
# ─────────────────────────────────────────────

run: env-check
	@echo "🌐 Launching Hybrid Audio API..."
	@$(ACTIVATE) && uvicorn fastapi_server:app --reload --host 0.0.0.0 --port $(PORT)

run-prod: env-check
	@echo "🚀 Launching Hybrid Audio API (no reload)..."
	@$(ACTIVATE) && uvicorn fastapi_server:app --host 0.0.0.0 --port $(PORT)

restart:
	@echo "🔁 Restarting server..."
	pkill -f "uvicorn" || true
	sleep 1
	make run

# ─────────────────────────────────────────────
# SECTION 2 — CLI INTEGRATION (v5.1)
# ─────────────────────────────────────────────

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

# ─────────────────────────────────────────────
# SECTION 3 — BATCH GENERATION (rotations + templates)
# ─────────────────────────────────────────────

batch-rotations: env-check
	@echo "🔁 Generating rotational stems (offline, Sonic-3 aligned)..."
	@$(ACTIVATE) && $(PYTHON) -c "from pathlib import Path; from batch_generate_stems import generate_rotational_stems; generate_rotational_stems(Path('data/common_names.json'), Path('data/developer_names.json'))"
	@echo "✅ Rotational batch complete."

batch-template: env-check
	@echo "📜 Generating template stems (double_anchor_hybrid_v3_5)..."
	@$(ACTIVATE) && $(PYTHON) -c "from batch_generate_stems import generate_from_template; generate_from_template('templates/double_anchor_hybrid_v3_5.json', first_name='John', developer='Hilton', max_workers=4)"
	@echo "✅ Template stems ready."

batch-outputs: env-check
	@echo "🎧 Generating full outputs for all name/developer pairs (may be heavy)..."
	@$(ACTIVATE) && $(PYTHON) -c "import json; from itertools import product; from pathlib import Path; from config import BASE_DIR; from assemble_message import assemble_pipeline; names=json.loads((BASE_DIR/'data/common_names.json').read_text())['items']; devs=json.loads((BASE_DIR/'data/developer_names.json').read_text())['items']; [assemble_pipeline(n, d, clean_merge=True, template_name='double_anchor_hybrid_v3_5.json') for n, d in product(names, devs)]"
	@echo "✅ Batch outputs complete."

# ─────────────────────────────────────────────
# SECTION 4 — DATASET / ROTATION AUDITS
# ─────────────────────────────────────────────

batch-validate: env-check
	@echo "Validating cache integrity (count stems)..."
	@$(ACTIVATE) && $(PYTHON) -c "import os; from config import STEMS_DIR; print('Total stems →', len(list(os.listdir(STEMS_DIR))))"

batch-audit: env-check
	@echo "Auditing dataset coverage vs stems..."
	@$(ACTIVATE) && $(PYTHON) -c "import json, os; from pathlib import Path; from config import BASE_DIR, STEMS_DIR; names=json.load(open(BASE_DIR/'data/common_names.json'))['items']; devs=json.load(open(BASE_DIR/'data/developer_names.json'))['items']; cached=[p.stem for p in Path(STEMS_DIR).glob('*.wav')]; missing_names=[n for n in names if n.lower() not in str(cached).lower()]; missing_devs=[d for d in devs if d.lower() not in str(cached).lower()]; print('Missing name stems:', len(missing_names)); print('Missing developer stems:', len(missing_devs))"

rotation-stats: env-check
	@echo "📊 Rotational engine stats..."
	@$(ACTIVATE) && $(PYTHON) -c "import json; from rotational_engine import rotation_stats; print(json.dumps(rotation_stats(), indent=2, ensure_ascii=False))"

# ─────────────────────────────────────────────
# SECTION 5 — TEST SUITE (HTTP)
# ─────────────────────────────────────────────

test-template: env-check
	@echo "Testing /assemble/template (Sonic-3)..."
	@$(ACTIVATE) && curl -s -X POST "http://$(HOST):$(PORT)/assemble/template?extended=true" \
		-H "Content-Type: application/json" \
		-d '{"first_name":"John","developer":"Hilton","template":"double_anchor_hybrid_v3_5.json","upload":false}' | jq .

test-unified: env-check
	@echo "Testing extended pipeline via /assemble/template (proxy for unified E2E)..."
	@$(ACTIVATE) && curl -s -X POST "http://$(HOST):$(PORT)/assemble/template?extended=true" \
		-H "Content-Type: application/json" \
		-d '{"first_name":"Maria","developer":"Marriott","template":"double_anchor_hybrid_v3_5.json","upload":false}' | jq .

test-cache-list: env-check
	@echo "Testing /cache/list (extended)..."
	@$(ACTIVATE) && curl -s "http://$(HOST):$(PORT)/cache/list?extended=true" | jq .

test-rotation: env-check
	@echo "Testing /rotation/next_pair..."
	@$(ACTIVATE) && curl -s "http://$(HOST):$(PORT)/rotation/next_pair" | jq .

test-health: env-check
	@echo "Testing /health/extended..."
	@$(ACTIVATE) && curl -s "http://$(HOST):$(PORT)/health/extended" | jq .

test-merge: env-check
	@echo "🔍 Verifying stem format integrity (bitmerge_semantic.verify_integrity)..."
	@$(ACTIVATE) && $(PYTHON) -c "from bitmerge_semantic import verify_integrity; verify_integrity('stems')"

# ─────────────────────────────────────────────
# SECTION 6 — GCS AUDIT
# ─────────────────────────────────────────────

audit-upload:
	@echo "Uploading test file to GCS..."
	@$(ACTIVATE) && $(PYTHON) gcs_audit.py upload stems/test.wav || true

audit-list:
	@$(ACTIVATE) && $(PYTHON) gcs_audit.py list || true

audit-bucket:
	@$(ACTIVATE) && $(PYTHON) gcs_audit.py bucket || true

audit-stems:
	@echo "Listing stem-specific GCS audits..."
	@$(ACTIVATE) && $(PYTHON) gcs_audit.py stems || true

audit-outputs:
	@echo "Listing output-specific GCS audits..."
	@$(ACTIVATE) && $(PYTHON) gcs_audit.py outputs || true

audit-cloud: audit-upload audit-list audit-bucket
	@echo "Cloud audit complete."

# ─────────────────────────────────────────────
# SECTION 7 — STEMS / OUTPUT MANAGEMENT
# ─────────────────────────────────────────────

outputs:
	@echo "Local outputs:"
	@ls -lh output/*.wav || true

stems-tree:
	@echo "Stems folder structure:"
	tree stems || true

stems-info:
	@$(ACTIVATE) && $(PYTHON) -c "from audio_utils import read_info; print(read_info('stems/$(stem)'))"

# ─────────────────────────────────────────────
# SECTION 8 — CLEANUP
# ─────────────────────────────────────────────

clean:
	@echo "Cleaning..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find output -type f -name "*.wav" -delete
	@echo "Cleanup done."

# ─────────────────────────────────────────────
# SECTION 9 — HELP
# ─────────────────────────────────────────────

help:
	@echo ""
	@echo "Hybrid Audio API — v5.1 (Sonic-3 / Router Edition)"
	@echo "──────────────────────────────────────────────"
	@echo "make init              → Prepare environment"
	@echo "make run               → Start FastAPI server (reload)"
	@echo "make run-prod          → Start FastAPI server (no reload)"
	@echo "make cli ARGS=\"...\"  → Run CLI"
	@echo "make cli-generate ...  → Proxy generate commands"
	@echo "make cli-assemble ...  → Proxy assemble commands"
	@echo "make cli-rotation ...  → Proxy rotation commands"
	@echo "make cli-cache ...     → Proxy cache commands"
	@echo "make cli-external ...  → Proxy external dataset commands"
	@echo ""
	@echo "make batch-rotations   → Generate rotational stems (offline)"
	@echo "make batch-template    → Generate template stems"
	@echo "make batch-outputs     → Generate full outputs for all pairs"
	@echo ""
	@echo "make batch-validate    → Count stems in cache dir"
	@echo "make batch-audit       → Coverage audit vs datasets"
	@echo "make rotation-stats    → Show rotational engine stats"
	@echo ""
	@echo "make test-template     → Test /assemble/template"
	@echo "make test-unified      → Extended template test (E2E proxy)"
	@echo "make test-cache-list   → Test /cache/list"
	@echo "make test-rotation     → Test /rotation/next_pair"
	@echo "make test-health       → Test /health/extended"
	@echo "make test-merge        → Verify stems integrity"
	@echo ""
	@echo "make audit-cloud       → GCS upload + list + bucket"
	@echo "make audit-stems       → View stem GCS audits"
	@echo "make audit-outputs     → View output GCS audits"
	@echo ""
	@echo "make outputs           → List local output WAVs"
	@echo "make stems-tree        → Tree of stems"
	@echo "make stems-info stem=… → Inspect one stem"
	@echo "make clean             → Clean temp artifacts"
	@echo ""
