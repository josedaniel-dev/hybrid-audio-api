#!/usr/bin/env python3
"""
CLI.py — Hybrid Audio API v5.1
NDF-SAFE — Full Sonic-3 Contract + Router Alignment

Features:
• Uses HTTP routers (no internal imports)
• Regenerated for v5.1 routes (generate / assemble / rotation / cache / external)
• Adds extended=true support for debugging
• Adds bucket verifiers
• Removes deprecated force_regen and legacy assemble calls
• Fully aligned with normalized labels:
      stem.name.<name>
      stem.developer.<developer>
"""

import argparse
import sys
import json
import requests
from pathlib import Path
from typing import Any, Dict

from config import (
    STEMS_DIR,
    OUTPUT_DIR,
    COMMON_NAMES_FILE,
    DEVELOPER_NAMES_FILE,
)

API = "http://127.0.0.1:8000"


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────
def _j(x):
    print(json.dumps(x, indent=2, ensure_ascii=False))


def _ensure_dirs():
    STEMS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


# ────────────────────────────────────────────────
# Generate
# ────────────────────────────────────────────────

def cmd_gen_name(args):
    payload = {
        "name": args.name.title(),
        "voice_id": args.voice_id,
    }
    r = requests.post(f"{API}/generate/name?extended={args.extended}", json=payload)
    _j(r.json())


def cmd_gen_dev(args):
    payload = {
        "developer": args.developer.title(),
        "voice_id": args.voice_id,
    }
    r = requests.post(f"{API}/generate/developer?extended={args.extended}", json=payload)
    _j(r.json())


def cmd_gen_combined(args):
    payload = {
        "name": args.name.title(),
        "developer": args.developer.title(),
        "voice_id": args.voice_id,
    }
    r = requests.post(f"{API}/generate/combined?extended={args.extended}", json=payload)
    _j(r.json())


# ────────────────────────────────────────────────
# Assemble
# ────────────────────────────────────────────────

def cmd_ass_template(args):
    payload = {
        "first_name": args.name.title(),
        "developer": args.developer.title(),
        "template": args.template,
        "upload": args.upload,
    }
    r = requests.post(f"{API}/assemble/template?extended={args.extended}", json=payload)
    _j(r.json())


def cmd_ass_raw(args):
    payload = {
        "segments": args.stems,
        "upload": args.upload,
    }
    r = requests.post(f"{API}/assemble/segments", json=payload)
    _j(r.json())


def cmd_ass_outloc(args):
    r = requests.get(f"{API}/assemble/output_location")
    _j(r.json())


# ────────────────────────────────────────────────
# Rotation
# ────────────────────────────────────────────────

def cmd_rot_next_name(args):
    r = requests.get(f"{API}/rotation/next_name")
    _j(r.json())


def cmd_rot_next_dev(args):
    r = requests.get(f"{API}/rotation/next_developer")
    _j(r.json())


def cmd_rot_next_pair(args):
    r = requests.get(f"{API}/rotation/next_pair")
    _j(r.json())


def cmd_rot_generate(args):
    payload = {"voice_id": args.voice_id}
    r = requests.post(f"{API}/rotation/generate_pair?extended={args.extended}", json=payload)
    _j(r.json())


def cmd_rot_stream(args):
    r = requests.get(f"{API}/rotation/pairs_stream?limit={args.limit}")
    _j(r.json())


# ────────────────────────────────────────────────
# Cache
# ────────────────────────────────────────────────

def cmd_cache_list(args):
    r = requests.get(f"{API}/cache/list?extended={args.extended}")
    _j(r.json())


def cmd_cache_invalidate(args):
    payload = {"stem_name": args.stem}
    r = requests.post(f"{API}/cache/invalidate", json=payload)
    _j(r.json())


def cmd_cache_bulk(args):
    payload = {
        "names_path": args.names or str(COMMON_NAMES_FILE),
        "developers_path": args.developers or str(DEVELOPER_NAMES_FILE),
    }
    r = requests.post(f"{API}/cache/bulk_generate", json=payload)
    _j(r.json())


# ────────────────────────────────────────────────
# External dataset intake
# ────────────────────────────────────────────────

def cmd_ext_upload(args):
    files = {"file": open(args.path, "rb")}
    data = {"dataset_role": args.role, "target_name": args.target}
    r = requests.post(f"{API}/external/upload_base", files=files, data=data)
    _j(r.json())


def cmd_ext_preview(args):
    files = {"file": open(args.path, "rb")}
    r = requests.post(f"{API}/external/preview", files=files)
    _j(r.json())


# ────────────────────────────────────────────────
# Parser
# ────────────────────────────────────────────────

def build():
    p = argparse.ArgumentParser(
        prog="CLI.py",
        description="Hybrid Audio API — CLI Orchestrator (v5.1)",
    )

    sub = p.add_subparsers(dest="cmd", required=True)

    # ─ generate ─
    g = sub.add_parser("generate")
    gs = g.add_subparsers(dest="type", required=True)

    g1 = gs.add_parser("name")
    g1.add_argument("name")
    g1.add_argument("--voice_id")
    g1.add_argument("--extended", action="store_true")
    g1.set_defaults(func=cmd_gen_name)

    g2 = gs.add_parser("developer")
    g2.add_argument("developer")
    g2.add_argument("--voice_id")
    g2.add_argument("--extended", action="store_true")
    g2.set_defaults(func=cmd_gen_dev)

    g3 = gs.add_parser("combined")
    g3.add_argument("name")
    g3.add_argument("developer")
    g3.add_argument("--voice_id")
    g3.add_argument("--extended", action="store_true")
    g3.set_defaults(func=cmd_gen_combined)

    # ─ assemble ─
    a = sub.add_parser("assemble")
    asub = a.add_subparsers(dest="atype", required=True)

    a1 = asub.add_parser("template")
    a1.add_argument("name")
    a1.add_argument("developer")
    a1.add_argument("--template", required=True)
    a1.add_argument("--upload", action="store_true")
    a1.add_argument("--extended", action="store_true")
    a1.set_defaults(func=cmd_ass_template)

    a2 = asub.add_parser("raw")
    a2.add_argument("stems", nargs="+")
    a2.add_argument("--upload", action="store_true")
    a2.set_defaults(func=cmd_ass_raw)

    a3 = asub.add_parser("output_location")
    a3.set_defaults(func=cmd_ass_outloc)

    # ─ rotation ─
    r = sub.add_parser("rotation")
    rs = r.add_subparsers(dest="rtype", required=True)

    rs.add_parser("next_name").set_defaults(func=cmd_rot_next_name)
    rs.add_parser("next_developer").set_defaults(func=cmd_rot_next_dev)
    rs.add_parser("next_pair").set_defaults(func=cmd_rot_next_pair)

    r4 = rs.add_parser("generate_pair")
    r4.add_argument("--voice_id")
    r4.add_argument("--extended", action="store_true")
    r4.set_defaults(func=cmd_rot_generate)

    r5 = rs.add_parser("stream")
    r5.add_argument("--limit", type=int, default=10)
    r5.set_defaults(func=cmd_rot_stream)

    # ─ cache ─
    c = sub.add_parser("cache")
    cs = c.add_subparsers(dest="ctype", required=True)

    cl = cs.add_parser("list")
    cl.add_argument("--extended", action="store_true")
    cl.set_defaults(func=cmd_cache_list)

    ci = cs.add_parser("invalidate")
    ci.add_argument("stem")
    ci.set_defaults(func=cmd_cache_invalidate)

    cb = cs.add_parser("bulk")
    cb.add_argument("--names")
    cb.add_argument("--developers")
    cb.set_defaults(func=cmd_cache_bulk)

    # ─ external ─
    e = sub.add_parser("external")
    es = e.add_subparsers(dest="etype", required=True)

    e1 = es.add_parser("upload")
    e1.add_argument("path")
    e1.add_argument("--role", choices=["names", "developers", "custom"], default="custom")
    e1.add_argument("--target")
    e1.set_defaults(func=cmd_ext_upload)

    e2 = es.add_parser("preview")
    e2.add_argument("path")
    e2.set_defaults(func=cmd_ext_preview)

    return p


# ────────────────────────────────────────────────
def main(argv=None):
    parser = build()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
