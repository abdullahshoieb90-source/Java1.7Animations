#!/usr/bin/env python3
"""
Package the resource pack into installable .mcpack archives.

A Bedrock resource pack is just a zip with a manifest.json at its root, so this
script does not need the game to build one. Subpacks are merged into the
archive when `--split` is used, producing one archive per subpack selection
(the same idea as a "split install pack").

    python3 tools/build_mcpack.py                     # one pack, subpacks kept
    python3 tools/build_mcpack.py --split             # one archive per subpack, merged
    python3 tools/build_mcpack.py --out build/x.mcpack
    python3 tools/build_mcpack.py --skip-check        # skip validation

Archives are written to `artifacts/` by default, which is git-ignored.
Output is deterministic: entries are sorted and timestamps are pinned, so
rebuilding an unchanged pack yields the same bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pack_check  # noqa: E402

ROOT = pack_check.ROOT
DEFAULT_OUT_DIR = os.path.join(ROOT, "artifacts")
ZIP_TIMESTAMP = (2020, 1, 1, 0, 0, 0)

# Never ship these inside a pack archive.
EXCLUDE_DIRS = {
    ".git",
    ".vscode",
    ".github",
    "tools",
    "artifacts",
    "dist",
    "build",
    "__pycache__",
}
EXCLUDE_FILES = {".gitignore", "README.md", "CHANGELOG.md"}
EXCLUDE_SUFFIXES = (".py", ".pyc", ".md", ".mcpack", ".zip")


def collect_entries(root: str, merge_subpack: str | None, keep_subpacks: bool):
    entries = {}

    def walk(base, prefix=""):
        for dirpath, dirnames, filenames in os.walk(base):
            dirnames[:] = sorted(d for d in dirnames if d not in EXCLUDE_DIRS and not d.startswith("."))
            for name in sorted(filenames):
                if name in EXCLUDE_FILES or name.endswith(EXCLUDE_SUFFIXES) or name.startswith("."):
                    continue
                absolute = os.path.join(dirpath, name)
                rel = os.path.relpath(absolute, base).replace(os.sep, "/")
                entries[f"{prefix}{rel}"] = absolute

    walk(root)
    if not keep_subpacks:
        entries = {k: v for k, v in entries.items() if not k.startswith("subpacks/")}
    if merge_subpack:
        walk(os.path.join(root, "subpacks", merge_subpack))
    return entries


def rewrites_manifest(data: dict, merge_subpack: str | None, header_name: str | None):
    data = json.loads(json.dumps(data))  # deep copy
    if merge_subpack:
        data["subpacks"] = []
    header = data.setdefault("header", {})
    if header_name:
        header["name"] = header_name
    elif merge_subpack:
        header["name"] = f"{header.get('name', 'pack')} \u00a77[{merge_subpack}]\u00a7r"
    return data


def write_archive(out_path: str, entries: dict, root: str, merge_subpack: str | None, header_name: str | None):
    manifest = pack_check.load_json(os.path.join(root, "manifest.json"))
    manifest = rewrites_manifest(manifest, merge_subpack, header_name)
    manifest_bytes = json.dumps(manifest, indent=2, ensure_ascii=False).encode("utf-8")

    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    tmp_path = out_path + ".tmp"

    with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as zf:
        def put(name: str, data: bytes):
            info = zipfile.ZipInfo(name, date_time=ZIP_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, data)

        put("manifest.json", manifest_bytes)
        for name in sorted(entries):
            if name == "manifest.json":
                continue
            with open(entries[name], "rb") as fh:
                put(name, fh.read())

    os.replace(tmp_path, out_path)
    digest = hashlib.sha256(open(out_path, "rb").read()).hexdigest()
    return out_path, os.path.getsize(out_path), digest, len(entries)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Build .mcpack archives for this resource pack.")
    parser.add_argument("--root", default=ROOT, help="pack root (default: repo root)")
    parser.add_argument("--out", help="output archive path (default: artifacts/<name>.mcpack)")
    parser.add_argument("--split", action="store_true", help="build one merged archive per subpack")
    parser.add_argument("--name", help="override the manifest display name")
    parser.add_argument("--skip-check", action="store_true", help="do not run tools/pack_check.py first")
    parser.add_argument("--strict", action="store_true", help="fail on validator warnings too")
    args = parser.parse_args(argv)

    root = os.path.abspath(args.root)

    if not args.skip_check:
        check_args = ["--root", root] + (["--strict"] if args.strict else [])
        code = pack_check.main(check_args)
        if code != 0:
            print("\nAborting: validation failed.", file=sys.stderr)
            return code

    manifest = pack_check.load_json(os.path.join(root, "manifest.json"))
    version = ".".join(str(p) for p in manifest["header"]["version"])
    base_name = f"Java1.7Animations_v{version}"
    out_dir = DEFAULT_OUT_DIR if args.out is None else None

    builds = []
    if args.split:
        for sp in manifest.get("subpacks") or []:
            folder = sp["folder_name"]
            out = args.out or os.path.join(out_dir, f"{base_name}_{folder}.mcpack")
            entries = collect_entries(root, merge_subpack=folder, keep_subpacks=False)
            builds.append(write_archive(out, entries, root, folder, args.name))
    else:
        out = args.out or os.path.join(out_dir, f"{base_name}.mcpack")
        entries = collect_entries(root, merge_subpack=None, keep_subpacks=True)
        builds.append(write_archive(out, entries, root, None, args.name))

    total = 0
    for path, size, digest, count in builds:
        total += size
        print(f"{os.path.relpath(path, root)}  {size / 1024:.1f} KiB  {count} files  sha256={digest[:16]}...")
    print(f"\n{len(builds)} archive(s), {total / 1024:.1f} KiB total")
    return 0


if __name__ == "__main__":
    sys.exit(main())
