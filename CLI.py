#!/usr/bin/env python3
"""
CLI.py — Hybrid Audio API v5.2
NDF-SAFE — Sonic-3 Contract + Router Alignment + Hardened

Features:
• Uses HTTP routers (no internal imports)
• v5.1/v5.2 routes (generate / assemble / rotation / cache / external)
• API base URL configurable via env: HYBRID_AUDIO_API_URL
• Internal security header support: X-Internal-API-Key from INTERNAL_API_KEY
• Global timeouts (CLI_TIMEOUT_SECONDS, default 90s)
• Extended=true support for debugging
• Bucket-ready (relies on backend)
• Strong error handling (status_code + network errors)
• Safe file handling for external uploads
"""

import argparse
import sys
import os
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

# ────────────────────────────────────────────────
# Configurable API + Security + Timeout
# ────────────────────────────────────────────────

API = os.getenv("HYBRID_AUDIO_API_URL", "http://127.0.0.1:8000")
INTERNAL_API_KEY = os.getenv("INTERNAL_API_KEY", "")
DEFAULT_TIMEOUT = float(os.getenv("CLI_TIMEOUT_SECONDS", "90"))


# ────────────────────────────────────────────────
# Helpers
# ────────────────────────────────────────────────

def _j(x: Any) -> None:
    print(json.dumps(x, indent=2, ensure_ascii=False))


def _ensure_dirs() -> None:
    STEMS_DIR.mkdir(exist_ok=True)
    OUTPUT_DIR.mkdir(exist_ok=True)


def _build_headers() -> Dict[str, str]:
    headers: Dict[str, str] = {}
    if INTERNAL_API_KEY:
        headers["X-Internal-API-Key"] = INTERNAL_API_KEY
    return headers


def _request(
    method: str,
    path: str,
    *,
    params: Dict[str, Any] | None = None,
    payload_json: Any | None = None,
    files: Dict[str, Any] | None = None,
    data: Dict[str, Any] | None = None,
) -> Any:
    """
    Hardened HTTP request wrapper:
      • Respects HYBRID_AUDIO_API_URL
      • Injects X-Internal-API-Key when set
      • Applies timeout
      • Fails noisily on network / HTTP errors
    """
    url = f"{API}{path}"
    headers = _build_headers()

    try:
        resp = requests.request(
            method=method.upper(),
            url=url,
            params=params,
            json=payload_json,
            files=files,
            data=data,
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        print(f"❌ Request failed: {exc}", file=sys.stderr)
        print(f"   → {method.upper()} {url}", file=sys.stderr)
        sys.exit(1)

    if not resp.ok:
        try:
            body = resp.json()
            body_str = json.dumps(body, indent=2, ensure_ascii=False)
        except Exception:
            body_str = resp.text

        print(f"❌ API error {resp.status_code} for {method.upper()} {url}", file=sys.stderr)
        if body_str:
            print(body_str, file=sys.stderr)
        sys.exit(1)

    # Expect JSON everywhere in this API
    try:
        return resp.json()
    except Exception:
        print(f"⚠️ Non-JSON response from {url}", file=sys.stderr)
        print(resp.text, file=sys.stderr)
        sys.exit(1)


# ────────────────────────────────────────────────
# Generate
# ────────────────────────────────────────────────

def cmd_gen_name(args: argparse.Namespace) -> None:
    payload = {
        "name": args.name.title(),
        "voice_id": args.voice_id,
    }
    result = _request(
        "POST",
        "/generate/name",
        params={"extended": bool(args.extended)},
        payload_json=payload,
    )
    _j(result)


def cmd_gen_dev(args: argparse.Namespace) -> None:
    payload = {
        "developer": args.developer.title(),
        "voice_id": args.voice_id,
    }
    result = _request(
        "POST",
        "/generate/developer",
        params={"extended": bool(args.extended)},
        payload_json=payload,
    )
    _j(result)


def cmd_gen_combined(args: argparse.Namespace) -> None:
    payload = {
        "name": args.name.title(),
        "developer": args.developer.title(),
        "voice_id": args.voice_id,
    }
    result = _request(
        "POST",
        "/generate/combined",
        params={"extended": bool(args.extended)},
        payload_json=payload,
    )
    _j(result)


# ────────────────────────────────────────────────
# Assemble
# ────────────────────────────────────────────────

def cmd_ass_template(args: argparse.Namespace) -> None:
    payload = {
        "first_name": args.name.title(),
        "developer": args.developer.title(),
        "template": args.template,
        "upload": bool(args.upload),
    }
    result = _request(
        "POST",
        "/assemble/template",
        params={"extended": bool(args.extended)},
        payload_json=payload,
    )
    _j(result)


def cmd_ass_raw(args: argparse.Namespace) -> None:
    payload = {
        "segments": args.stems,
        "upload": bool(args.upload),
    }
    # Extended mode opcional — solo si backend lo soporta
    result = _request(
        "POST",
        "/assemble/segments",
        payload_json=payload,
    )
    _j(result)


def cmd_ass_outloc(args: argparse.Namespace) -> None:
    result = _request("GET", "/assemble/output_location")
    _j(result)


# ────────────────────────────────────────────────
# Rotation (names/developers + scripts)
# ────────────────────────────────────────────────

def cmd_rot_next_name(args: argparse.Namespace) -> None:
    result = _request("GET", "/rotation/next_name")
    _j(result)


def cmd_rot_next_dev(args: argparse.Namespace) -> None:
    result = _request("GET", "/rotation/next_developer")
    _j(result)


def cmd_rot_next_pair(args: argparse.Namespace) -> None:
    result = _request("GET", "/rotation/next_pair")
    _j(result)


def cmd_rot_generate(args: argparse.Namespace) -> None:
    payload = {"voice_id": args.voice_id}
    result = _request(
        "POST",
        "/rotation/generate_pair",
        params={"extended": bool(args.extended)},
        payload_json=payload,
    )
    _j(result)


def cmd_rot_stream(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/rotation/pairs_stream",
        params={"limit": int(args.limit)},
    )
    _j(result)


# ── v5.2 Script rotation commands (additive) ──

def cmd_rot_next_script(args: argparse.Namespace) -> None:
    result = _request("GET", "/rotation/next_script")
    _j(result)


def cmd_rot_generate_script(args: argparse.Namespace) -> None:
    payload = {"voice_id": args.voice_id}
    result = _request(
        "POST",
        "/rotation/generate_script",
        params={"extended": bool(args.extended)},
        payload_json=payload,
    )
    _j(result)


def cmd_rot_scripts_stream(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/rotation/scripts_stream",
        params={"limit": int(args.limit)},
    )
    _j(result)


def cmd_rot_check_bucket(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/rotation/check_bucket",
        params={"label": args.label},
    )
    _j(result)


# ────────────────────────────────────────────────
# Cache
# ────────────────────────────────────────────────

def cmd_cache_list(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/cache/list",
        params={"extended": bool(args.extended)},
    )
    _j(result)


def cmd_cache_invalidate(args: argparse.Namespace) -> None:
    payload = {"stem_name": args.stem}
    result = _request("POST", "/cache/invalidate", payload_json=payload)
    _j(result)


def cmd_cache_bulk(args: argparse.Namespace) -> None:
    payload = {
        "names_path": args.names or str(COMMON_NAMES_FILE),
        "developers_path": args.developers or str(DEVELOPER_NAMES_FILE),
    }
    result = _request("POST", "/cache/bulk_generate", payload_json=payload)
    _j(result)


def cmd_cache_check_in_bucket(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/cache/check_in_bucket",
        params={"label": args.label},
    )
    _j(result)


def cmd_cache_bucket_list(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/cache/bucket_list",
        params={"prefix": args.prefix or ""},
    )
    _j(result)

def cmd_cache_check_many(args: argparse.Namespace) -> None:
    labels = ",".join(args.labels)
    result = _request(
        "GET",
        "/cache/check_many",
        params={"labels": labels},
    )
    _j(result)


def cmd_cache_consistency_report(args: argparse.Namespace) -> None:
    result = _request(
        "GET",
        "/cache/consistency_report",
    )
    _j(result)


def cmd_cache_verify_and_repair(args: argparse.Namespace) -> None:
    payload = {
        "labels": args.labels or []
    }
    result = _request(
        "POST",
        "/cache/verify_and_repair",
        payload_json=payload,
    )
    _j(result)


# ────────────────────────────────────────────────
# External dataset intake
# ────────────────────────────────────────────────

def _ensure_file_exists(path: str) -> Path:
    p = Path(path)
    if not p.exists() or not p.is_file():
        print(f"❌ File not found: {p}", file=sys.stderr)
        sys.exit(1)
    return p


def cmd_ext_upload(args: argparse.Namespace) -> None:
    p = _ensure_file_exists(args.path)
    with p.open("rb") as f:
        files = {"file": f}
        data = {
            "dataset_role": args.role,
            "target_name": args.target or "",
        }
        # requests.request with files -> no json param
        url = f"{API}/external/upload_base"
        headers = _build_headers()
        try:
            resp = requests.post(
                url,
                files=files,
                data=data,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            print(f"❌ Request failed: {exc}", file=sys.stderr)
            print(f"   → POST {url}", file=sys.stderr)
            sys.exit(1)

        if not resp.ok:
            try:
                body = resp.json()
                body_str = json.dumps(body, indent=2, ensure_ascii=False)
            except Exception:
                body_str = resp.text
            print(f"❌ API error {resp.status_code} for POST {url}", file=sys.stderr)
            if body_str:
                print(body_str, file=sys.stderr)
            sys.exit(1)

        try:
            result = resp.json()
        except Exception:
            print("⚠️ Non-JSON response from external/upload_base", file=sys.stderr)
            print(resp.text, file=sys.stderr)
            sys.exit(1)

    _j(result)


def cmd_ext_preview(args: argparse.Namespace) -> None:
    p = _ensure_file_exists(args.path)
    with p.open("rb") as f:
        files = {"file": f}
        url = f"{API}/external/preview"
        headers = _build_headers()
        try:
            resp = requests.post(
                url,
                files=files,
                headers=headers,
                timeout=DEFAULT_TIMEOUT,
            )
        except requests.RequestException as exc:
            print(f"❌ Request failed: {exc}", file=sys.stderr)
            print(f"   → POST {url}", file=sys.stderr)
            sys.exit(1)

        if not resp.ok:
            try:
                body = resp.json()
                body_str = json.dumps(body, indent=2, ensure_ascii=False)
            except Exception:
                body_str = resp.text
            print(f"❌ API error {resp.status_code} for POST {url}", file=sys.stderr)
            if body_str:
                print(body_str, file=sys.stderr)
            sys.exit(1)

        try:
            result = resp.json()
        except Exception:
            print("⚠️ Non-JSON response from external/preview", file=sys.stderr)
            print(resp.text, file=sys.stderr)
            sys.exit(1)

    _j(result)


def cmd_ext_list(args: argparse.Namespace) -> None:
    result = _request("GET", "/external/list")
    _j(result)


def cmd_ext_delete(args: argparse.Namespace) -> None:
    result = _request(
        "DELETE",
        "/external/delete",
        params={"filename": args.filename},
    )
    _j(result)


# ────────────────────────────────────────────────
# Parser
# ────────────────────────────────────────────────

def build() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="CLI.py",
        description="Hybrid Audio API — CLI Orchestrator (v5.2, hardened)",
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

    # v5.2 script-related rotation subcommands
    r6 = rs.add_parser("next_script")
    r6.set_defaults(func=cmd_rot_next_script)

    r7 = rs.add_parser("generate_script")
    r7.add_argument("--voice_id")
    r7.add_argument("--extended", action="store_true")
    r7.set_defaults(func=cmd_rot_generate_script)

    r8 = rs.add_parser("scripts_stream")
    r8.add_argument("--limit", type=int, default=10)
    r8.set_defaults(func=cmd_rot_scripts_stream)

    r9 = rs.add_parser("check_bucket")
    r9.add_argument("label")
    r9.set_defaults(func=cmd_rot_check_bucket)

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

    cc = cs.add_parser("check_in_bucket")
    cc.add_argument("label")
    cc.set_defaults(func=cmd_cache_check_in_bucket)

    cbl = cs.add_parser("bucket_list")
    cbl.add_argument("--prefix", default="")
    cbl.set_defaults(func=cmd_cache_bucket_list)

    c_many = cs.add_parser("check_many")
    c_many.add_argument("labels", nargs="+")
    c_many.set_defaults(func=cmd_cache_check_many)

    c_cons = cs.add_parser("consistency_report")
    c_cons.set_defaults(func=cmd_cache_consistency_report)

    c_fix = cs.add_parser("verify_and_repair")
    c_fix.add_argument("--labels", nargs="*")
    c_fix.set_defaults(func=cmd_cache_verify_and_repair)

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

    e3 = es.add_parser("list")
    e3.set_defaults(func=cmd_ext_list)

    e4 = es.add_parser("delete")
    e4.add_argument("filename")
    e4.set_defaults(func=cmd_ext_delete)

    return p


# ────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    _ensure_dirs()
    parser = build()
    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
